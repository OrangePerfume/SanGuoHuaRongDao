"""Bounded, atomic, separately ranked challenge best results (single writer)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from .challenge import ChallengeSession, ChallengeSpec
from .puzzles import PUZZLES

MAX_BYTES = 4096
MAX_MS = 10 * 365 * 24 * 60 * 60 * 1000
MAX_STEPS = (1 << 53) - 1


class InvalidChallengeRecord(ValueError):
    pass


class ChallengeRecords:
    """Caller must hold the application's existing progress.lock to write."""
    def __init__(self, directory: Path, spec: ChallengeSpec):
        self.spec = spec
        self.path = Path(directory) / f'challenge-{spec.puzzle}-{spec.mode}-{spec.difficulty}.json'

    def _validate(self, data: object) -> dict[str, int]:
        if not isinstance(data, dict) or data.get('schema') != 1 or type(data.get('schema')) is not int:
            raise InvalidChallengeRecord('Unknown challenge record format')
        steps, ms = data.get('steps'), data.get('milliseconds')
        if (type(steps) is not int or not PUZZLES[self.spec.puzzle].minimum_steps <= steps <= MAX_STEPS
                or type(ms) is not int or not 0 <= ms <= MAX_MS
                or (self.spec.mode == 'steps' and steps > self.spec.limit)
                or (self.spec.mode == 'time' and ms >= self.spec.limit * 1000)):
            raise InvalidChallengeRecord('Invalid challenge result')
        return {'steps': steps, 'milliseconds': ms}

    def load(self) -> dict[str, int]:
        try:
            with self.path.open('rb') as source:
                raw = source.read(MAX_BYTES + 1)
        except FileNotFoundError:
            return {}
        if len(raw) > MAX_BYTES:
            raise InvalidChallengeRecord('Challenge record too large')
        try:
            return self._validate(json.loads(raw.decode('utf-8')))
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise InvalidChallengeRecord('Invalid challenge record') from exc

    def _rank(self, result: dict[str, int]) -> tuple[int, int]:
        steps, ms = result['steps'], result['milliseconds']
        return (ms, steps) if self.spec.mode == 'time' else (steps, ms)

    def save_success(self, session: ChallengeSession) -> bool:
        if session.spec != self.spec or session.status != 'success' or not session.game.finished:
            raise ValueError('Only completed matching challenges can be recorded')
        if session.game.undo_count or session.game.hint_count:
            raise ValueError('Assisted challenge result')
        result = self._validate({'schema': 1, 'steps': session.game.steps,
                                 'milliseconds': int(session.elapsed * 1000)})
        old = self.load()  # Corrupt files are preserved, not overwritten.
        if old and self._rank(result) >= self._rank(old):
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                                             prefix='.challenge-', suffix='.tmp', delete=False) as dest:
                tmp = Path(dest.name)
                json.dump({'schema': 1, **result}, dest)
                dest.flush()
                os.fsync(dest.fileno())
            os.replace(tmp, self.path)
        finally:
            if tmp is not None:
                try:
                    tmp.unlink(missing_ok=True)
                except OSError:
                    pass
        return True
