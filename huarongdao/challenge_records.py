"""Bounded, atomic, separately ranked challenge best results (single writer)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from .challenge import ChallengeSession, ChallengeSpec, ChallengeStatus
from .core import won
from .puzzles import PUZZLES

MAX_BYTES = 4096
MAX_MS = 10 * 365 * 24 * 60 * 60 * 1000
MAX_STEPS = (1 << 53) - 1


class InvalidChallengeRecord(ValueError):
    pass


def _unique_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidChallengeRecord('Duplicate challenge record field')
        result[key] = value
    return result


class ChallengeRecords:
    """Caller must hold the application's existing progress.lock to write."""
    def __init__(self, directory: Path, spec: ChallengeSpec):
        self.spec = spec
        self.path = Path(directory) / f'challenge-r{spec.rule_version}-{spec.puzzle}-{spec.mode}-{spec.difficulty}.json'

    def _identity(self) -> dict:
        return {'schema': 2, 'rule_version': self.spec.rule_version,
                'puzzle': self.spec.puzzle, 'mode': self.spec.mode,
                'difficulty': self.spec.difficulty}

    def _validate(self, data: object) -> dict[str, int]:
        if (not isinstance(data, dict) or type(data.get('schema')) is not int
                or type(data.get('rule_version')) is not int
                or any(data.get(k) != v for k, v in self._identity().items())):
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
            return self._validate(json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_fields))
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise InvalidChallengeRecord('Invalid challenge record') from exc

    def _rank(self, result: dict[str, int]) -> tuple[int, int]:
        steps, ms = result['steps'], result['milliseconds']
        return (ms, steps) if self.spec.mode == 'time' else (steps, ms)

    def save_success(self, session: ChallengeSession) -> bool:
        snapshot = session.result
        if (snapshot is None or snapshot.spec != self.spec
                or snapshot.status != ChallengeStatus.SUCCESS or not won(snapshot.positions)):
            raise ValueError('Only completed matching challenges can be recorded')
        result = self._validate({**self._identity(), 'steps': snapshot.steps,
                                 'milliseconds': snapshot.milliseconds})
        old = self.load()  # Corrupt files are preserved, not overwritten.
        if old and self._rank(result) >= self._rank(old):
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                                             prefix='.challenge-', suffix='.tmp', delete=False) as dest:
                tmp = Path(dest.name)
                json.dump({**self._identity(), **result}, dest)
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
