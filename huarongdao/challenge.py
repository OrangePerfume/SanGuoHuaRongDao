"""Deterministic offline challenge rules, independent of the classic profile."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import time
from typing import Callable

from .core import BOARD_H, PIECES, shifted_group, won
from .model import GameModel
from .puzzles import DEFAULT_PUZZLE, PUZZLES

MODES = ('time', 'steps')
DIFFICULTIES = ('beginner', 'standard', 'expert', 'extreme')
RULE_VERSION = 1
STEP_RATIOS = ((2, 1), (3, 2), (6, 5), (1, 1))
CLASSIC_SECONDS = (900, 600, 300, 180)
_NS = 1_000_000_000


class ChallengeStatus(StrEnum):
    ACTIVE = 'active'
    SUCCESS = 'success'
    TIMEOUT = 'timeout'
    EXHAUSTED = 'exhausted'
    ABANDONED = 'abandoned'


@dataclass(frozen=True)
class ChallengeSpec:
    puzzle: str
    mode: str
    difficulty: str
    rule_version: int = RULE_VERSION

    def __post_init__(self):
        if (not isinstance(self.puzzle, str) or self.puzzle not in PUZZLES
                or self.mode not in MODES or self.difficulty not in DIFFICULTIES
                or type(self.rule_version) is not int or self.rule_version != RULE_VERSION):
            raise ValueError('Invalid challenge')

    @property
    def step_limit(self) -> int | None:
        if self.mode != 'steps':
            return None
        n, d = STEP_RATIOS[DIFFICULTIES.index(self.difficulty)]
        return (PUZZLES[self.puzzle].minimum_steps * n + d - 1) // d

    @property
    def time_limit(self) -> int | None:
        if self.mode != 'time':
            return None
        base = PUZZLES[DEFAULT_PUZZLE].minimum_steps * 15
        scaled = CLASSIC_SECONDS[DIFFICULTIES.index(self.difficulty)] * PUZZLES[self.puzzle].minimum_steps
        return max(60, ((scaled + base - 1) // base) * 15)

    @property
    def limit(self) -> int:
        # Retain the existing single-constraint GUI interface.
        return self.step_limit if self.mode == 'steps' else self.time_limit


@dataclass(frozen=True)
class ChallengeResult:
    spec: ChallengeSpec
    status: ChallengeStatus
    steps: int
    milliseconds: int
    positions: tuple[int, ...]


class ChallengeSession:
    """Single-threaded session; GUI model is a projection, never the authority.

    Only accepted legal moves advance the private state. Terminal results are
    frozen once. Deadlines are sampled before committing each single-cell move.
    """
    def __init__(self, spec: ChallengeSpec, clock: Callable[[], float] = time.monotonic):
        self._spec = spec
        self._clock = clock
        self._game = GameModel(clock=clock)
        self._game.select_puzzle(spec.puzzle)
        self._positions = self._game.positions
        self._steps = 0
        self._start = self._now()
        self._last = self._start
        self._result: ChallengeResult | None = None

    def _now(self) -> int:
        return round(self._clock() * _NS)

    def _sample(self) -> int:
        self._last = max(self._last, self._now())
        return self._last

    @property
    def spec(self) -> ChallengeSpec:
        return self._spec

    @property
    def game(self) -> GameModel:
        return self._game

    @property
    def result(self) -> ChallengeResult | None:
        return self._result

    @property
    def status(self) -> ChallengeStatus:
        return ChallengeStatus.ACTIVE if self._result is None else self._result.status

    @property
    def elapsed(self) -> float:
        if self._result is not None:
            return self._result.milliseconds / 1000
        return (self._sample() - self._start) / _NS

    @property
    def remaining(self) -> int:
        if self.spec.step_limit is not None:
            return max(0, self.spec.step_limit - self._steps)
        if self._result is not None:
            elapsed_ns = self._result.milliseconds * 1_000_000
        else:
            elapsed_ns = self._sample() - self._start
        return max(0, (self.spec.time_limit * _NS - elapsed_ns + _NS - 1) // _NS)

    def _finish(self, status: ChallengeStatus, now: int) -> None:
        if self._result is None:
            self._result = ChallengeResult(self.spec, status, self._steps,
                                           (now - self._start) // 1_000_000, self._positions)

    def _projection_matches(self) -> bool:
        g = self._game
        return (g.puzzle_id == self.spec.puzzle and g.positions == self._positions
                and type(g.steps) is int and g.steps == self._steps and not g.paused
                and not g.history and not g.history_costs and not g.undo_count and not g.hint_count)

    def _restore_projection(self) -> None:
        g = self._game
        g.select_puzzle(self.spec.puzzle)
        g.positions, g.steps = self._positions, self._steps

    def _check(self, now: int) -> ChallengeStatus:
        # The existing GUI may read GameModel. Accidental outside mutations
        # invalidate an active challenge and cannot fabricate a valid result.
        if not self._projection_matches():
            self._restore_projection()
            self._finish(ChallengeStatus.ABANDONED, now)
        if self._result is None:
            limit = self.spec.time_limit
            if limit is not None and now - self._start >= limit * _NS:
                self._finish(ChallengeStatus.TIMEOUT, self._start + limit * _NS)
            elif won(self._positions):
                self._finish(ChallengeStatus.SUCCESS, now)
            elif self.spec.step_limit is not None and self._steps >= self.spec.step_limit:
                self._finish(ChallengeStatus.EXHAUSTED, now)
        return self.status

    def poll(self) -> ChallengeStatus:
        return self._check(self._sample())

    def move(self, indices: tuple[int, ...], dx: int, dy: int, count: int = 1) -> int:
        if (self.poll() != ChallengeStatus.ACTIVE or type(count) is not int or count < 1
                or not isinstance(indices, tuple) or not 1 <= len(indices) <= len(PIECES)
                or any(type(i) is not int or not 0 <= i < len(PIECES) for i in indices)
                or len(set(indices)) != len(indices)
                or type(dx) is not int or type(dy) is not int or abs(dx) + abs(dy) != 1):
            return 0
        moved = 0
        for _ in range(min(count, BOARD_H)):
            if self.poll() != ChallengeStatus.ACTIVE:
                break
            if self.spec.step_limit is not None and self.remaining < len(indices):
                break
            after = shifted_group(self._positions, indices, dx, dy)
            if after is None:
                break
            # Do not commit a move whose validation crossed the deadline.
            now = self._sample()
            if self._check(now) != ChallengeStatus.ACTIVE:
                break
            self._positions, self._steps = after, self._steps + len(indices)
            self._game.positions, self._game.steps = self._positions, self._steps
            moved += 1
            if self._check(now) != ChallengeStatus.ACTIVE:
                break
        return moved

    def abandon(self) -> None:
        now = self._sample()
        self._check(now)
        self._finish(ChallengeStatus.ABANDONED, now)
