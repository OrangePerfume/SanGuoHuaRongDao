"""Deterministic offline challenge rules; no GUI or classic profile dependency."""
from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Callable

from .core import PIECES
from .model import GameModel
from .puzzles import PUZZLES

MODES = ('time', 'steps')
DIFFICULTIES = ('beginner', 'standard', 'expert', 'extreme')
# Ratios use integer arithmetic, avoiding rounding differences across platforms.
STEP_RATIOS = ((2, 1), (3, 2), (6, 5), (1, 1))
CLASSIC_SECONDS = (900, 600, 300, 180)


@dataclass(frozen=True)
class ChallengeSpec:
    puzzle: str
    mode: str
    difficulty: str

    def __post_init__(self):
        if (not isinstance(self.puzzle, str) or self.puzzle not in PUZZLES
                or self.mode not in MODES or self.difficulty not in DIFFICULTIES):
            raise ValueError('Invalid challenge')

    @property
    def limit(self) -> int:
        index = DIFFICULTIES.index(self.difficulty)
        minimum = PUZZLES[self.puzzle].minimum_steps
        if self.mode == 'steps':
            n, d = STEP_RATIOS[index]
            return (minimum * n + d - 1) // d
        # Scale by solver distance, rounded up to a 15-second boundary.
        return max(60, ((CLASSIC_SECONDS[index] * minimum + 116 * 15 - 1) // (116 * 15)) * 15)


class ChallengeSession:
    """A separate board and monotonic deadline, with immutable terminal outcome.

    No pause, undo or hint API. Call move for each input and poll on timer ticks.
    A finish exactly at the deadline fails; a finish at the step cap succeeds.
    """
    def __init__(self, spec: ChallengeSpec, clock: Callable[[], float] = time.monotonic):
        self.spec = spec
        self._clock = clock
        self.game = GameModel(clock=clock)
        self.game.select_puzzle(spec.puzzle)
        self._start = clock()
        self._end: float | None = None
        self.status = 'active'

    @property
    def elapsed(self) -> float:
        return max(0.0, (self._clock() if self._end is None else self._end) - self._start)

    @property
    def remaining(self) -> int:
        if self.spec.mode == 'steps':
            return max(0, self.spec.limit - self.game.steps)
        return max(0, math.ceil(self.spec.limit - self.elapsed))

    def _finish(self, status: str, now: float) -> None:
        if self.status == 'active':
            self.status = status
            self._end = now

    def poll(self) -> str:
        if self.status != 'active':
            return self.status
        now = self._clock()
        if self.spec.mode == 'time' and now - self._start >= self.spec.limit:
            self._finish('timeout', self._start + self.spec.limit)
        elif self.game.finished:
            self._finish('success', now)
        elif self.spec.mode == 'steps' and self.game.steps >= self.spec.limit:
            self._finish('exhausted', now)
        return self.status

    def move(self, indices: tuple[int, ...], dx: int, dy: int, count: int = 1) -> int:
        if (self.poll() != 'active' or type(count) is not int or count < 1
                or not isinstance(indices, tuple) or not indices
                or any(type(i) is not int or not 0 <= i < len(PIECES) for i in indices)
                or len(set(indices)) != len(indices)
                or type(dx) is not int or type(dy) is not int or abs(dx) + abs(dy) != 1):
            return 0
        moved = 0
        # A board is at most five cells tall; bound the loop even for invalid callers.
        for _ in range(min(count, 5)):
            if self.poll() != 'active':
                break
            if self.spec.mode == 'steps' and self.remaining < len(indices):
                break
            if not self.game.move_group(indices, dx, dy, 1):
                break
            moved += 1
            if self.poll() != 'active':
                break
        return moved

    def abandon(self) -> None:
        self.poll()
        self._finish('abandoned', self._clock())
