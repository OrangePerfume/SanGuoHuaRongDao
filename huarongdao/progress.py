"""Bounded, versioned local session snapshots and achievement-ready statistics."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import tempfile
from dataclasses import dataclass, field

from .core import BOARD_W, BOARD_H, PIECES, shifted_group, valid, won
from .model import GameModel
from .puzzles import PUZZLES

SCHEMA = 1
MAX_BYTES = 2 * 1024 * 1024
MAX_HISTORY = 20_000
MAX_COUNTER = (1 << 53) - 1
MAX_ELAPSED = 10 * 365 * 24 * 60 * 60
COUNTERS = ('moves', 'undos', 'hints', 'wins', 'unassisted_wins', 'optimal_wins')


class InvalidProgress(ValueError):
    """An unreadable or unsupported progress file; preserve it for recovery."""


def _counter(value: object) -> int:
    if type(value) is not int or not 0 <= value <= MAX_COUNTER:
        raise InvalidProgress('Invalid counter')
    return value


def _positions(value: object) -> tuple[int, ...]:
    if not isinstance(value, list) or len(value) != len(PIECES):
        raise InvalidProgress('Invalid board length')
    if any(type(pos) is not int or not 0 <= pos < BOARD_W * BOARD_H for pos in value):
        raise InvalidProgress('Invalid board cell')
    board = tuple(value)
    if not valid(board):
        raise InvalidProgress('Invalid board')
    return board


def _transition_cost(before: tuple[int, ...], after: tuple[int, ...]) -> int:
    """Validate an undo unit, including every intermediate group position."""
    if won(before):
        raise InvalidProgress('History continues after completion')
    changed = tuple(i for i, (a, b) in enumerate(zip(before, after)) if a != b)
    if not changed:
        raise InvalidProgress('Empty history action')
    i = changed[0]
    dx = after[i] % BOARD_W - before[i] % BOARD_W
    dy = after[i] // BOARD_W - before[i] // BOARD_W
    count = abs(dx) + abs(dy)
    if not count or (dx and dy) or (len(changed) == 1 and count != 1):
        raise InvalidProgress('Invalid move distance')
    if shifted_group(before, changed, dx // count, dy // count, count) != after:
        raise InvalidProgress('Illegal move in history')
    # A group action stops immediately upon reaching the goal.
    if any(won(shifted_group(before, changed, dx // count, dy // count, n))
           for n in range(1, count)):
        raise InvalidProgress('Move continues after completion')
    return count * len(changed)


def snapshot(game: GameModel) -> dict:
    return {'puzzle': game.puzzle_id, 'positions': list(game.positions),
            'history': [list(p) for p in game.history], 'costs': list(game.history_costs),
            'steps': game.steps, 'elapsed': game.elapsed, 'undo_count': game.undo_count,
            'hint_count': game.hint_count, 'completion_recorded': game.completion_recorded}


def restore_snapshot(game: GameModel, data: object) -> None:
    """Validate completely before mutating the live model. Never restore wall-clock time."""
    if not isinstance(data, dict):
        raise InvalidProgress('Invalid snapshot')
    puzzle = data.get('puzzle')
    if not isinstance(puzzle, str) or puzzle not in PUZZLES:
        raise InvalidProgress('Unknown puzzle')
    board = _positions(data.get('positions'))
    raw_history, raw_costs = data.get('history'), data.get('costs')
    if (not isinstance(raw_history, list) or not isinstance(raw_costs, list)
            or len(raw_history) != len(raw_costs) or len(raw_history) > MAX_HISTORY):
        raise InvalidProgress('Invalid history length')
    history = [_positions(p) for p in raw_history]
    costs = [_counter(c) for c in raw_costs]
    steps = _counter(data.get('steps'))
    if (history[0] if history else board) != PUZZLES[puzzle].positions:
        raise InvalidProgress('History does not start at the opening')
    for before, after, cost in zip(history, history[1:] + [board], costs):
        if _transition_cost(before, after) != cost:
            raise InvalidProgress('Invalid history cost')
    if sum(costs) != steps:
        raise InvalidProgress('Invalid step total')
    elapsed = data.get('elapsed')
    if (type(elapsed) not in (int, float) or not 0 <= elapsed <= MAX_ELAPSED
            or not math.isfinite(elapsed) or (not steps and elapsed != 0)):
        raise InvalidProgress('Invalid elapsed time')
    undos, hints = _counter(data.get('undo_count')), _counter(data.get('hint_count'))
    recorded = data.get('completion_recorded')
    if type(recorded) is not bool:
        raise InvalidProgress('Invalid completion marker')
    game.select_puzzle(puzzle)
    game.positions, game.history, game.history_costs = board, history, costs
    game.steps, game._elapsed = steps, float(elapsed)
    game.paused = bool(steps and not game.finished)
    game._running_since = None
    game.undo_count, game.hint_count, game.completion_recorded = undos, hints, recorded


@dataclass
class Profile:
    """Counters for actual play since this schema was introduced; no invented legacy wins."""
    stats: dict[str, dict[str, int]] = field(default_factory=lambda: {
        puzzle: dict.fromkeys(COUNTERS, 0) for puzzle in PUZZLES})

    @classmethod
    def from_data(cls, data: object) -> Profile:
        if not isinstance(data, dict) or set(data) != set(PUZZLES):
            raise InvalidProgress('Invalid statistics puzzle keys')
        values = {}
        for puzzle, row in data.items():
            if not isinstance(row, dict) or set(row) != set(COUNTERS):
                raise InvalidProgress('Invalid statistics counters')
            values[puzzle] = {key: _counter(value) for key, value in row.items()}
            if max(row['unassisted_wins'], row['optimal_wins']) > row['wins']:
                raise InvalidProgress('Invalid completion counts')
        return cls(values)

    def add(self, puzzle: str, key: str, amount: int = 1) -> None:
        if type(amount) is not int or amount < 0:
            raise ValueError('Invalid counter increment')
        row = self.stats[puzzle]
        row[key] = min(MAX_COUNTER, row[key] + amount)

    def record_completion(self, game: GameModel) -> bool:
        if not game.finished or game.completion_recorded:
            return False
        game.completion_recorded = True
        self.add(game.puzzle_id, 'wins')
        if not game.undo_count and not game.hint_count:
            self.add(game.puzzle_id, 'unassisted_wins')
            if game.steps == PUZZLES[game.puzzle_id].minimum_steps:
                self.add(game.puzzle_id, 'optimal_wins')
        return True


class ProgressStore:
    """One atomic document keeps the active attempt and aggregate statistics together."""
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self, game: GameModel) -> Profile:
        try:
            with self.path.open('rb') as stream:
                raw = stream.read(MAX_BYTES + 1)
        except FileNotFoundError:
            return Profile()
        if len(raw) > MAX_BYTES:
            raise InvalidProgress('Progress file too large')
        try:
            data = json.loads(raw.decode('utf-8'))
            if not isinstance(data, dict) or type(data.get('schema')) is not int or data['schema'] != SCHEMA:
                raise InvalidProgress('Unsupported progress schema')
            profile = Profile.from_data(data.get('stats'))
            restore_snapshot(game, data.get('active'))
            return profile
        except (ValueError, TypeError, RecursionError, OverflowError) as exc:
            raise InvalidProgress('Invalid progress file') from exc

    def save(self, game: GameModel, profile: Profile) -> None:
        if len(game.history) > MAX_HISTORY:
            raise InvalidProgress('History exceeds storage limit')
        raw = json.dumps({'schema': SCHEMA, 'active': snapshot(game), 'stats': profile.stats},
                         ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
        if len(raw) > MAX_BYTES:
            raise InvalidProgress('Progress file too large')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(mode='wb', dir=self.path.parent,
                                             prefix='.progress-', suffix='.tmp', delete=False) as stream:
                tmp = Path(stream.name)
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, self.path)
        finally:
            if tmp is not None:
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass
