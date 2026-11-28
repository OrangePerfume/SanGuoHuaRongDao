"""Presentation-layer helpers; never modify the challenge rule engine or schema."""
from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from .challenge import ChallengeSpec, DIFFICULTIES, MODES
from .challenge_records import ChallengeRecords, InvalidChallengeRecord
from .puzzles import PUZZLES


class PreparationClock:
    """Freeze only before the UI is ready; after start, use the real clock."""
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.anchor = None

    def start(self):
        if self.anchor is None:
            self.anchor = self.clock()

    def __call__(self):
        return 0.0 if self.anchor is None else max(0.0, self.clock() - self.anchor)


def archive_invalid_record(store: ChallengeRecords) -> Path | None:
    """Caller holds the single writer lock. Never archive a valid/unreadable file."""
    try:
        store.load()
    except InvalidChallengeRecord:
        folder = Path(tempfile.mkdtemp(prefix='challenge-backup-', dir=store.path.parent))
        backup = folder / store.path.name
        try:
            os.replace(store.path, backup)
        except OSError:
            folder.rmdir()
            raise
        return backup
    return None


def read_challenge_overview(directory):
    """Read only known combinations; distinguish missing from unreadable records."""
    result = []
    for puzzle in PUZZLES:
        for mode in MODES:
            for difficulty in DIFFICULTIES:
                spec = ChallengeSpec(puzzle, mode, difficulty)
                try:
                    best = ChallengeRecords(directory, spec).load()
                except (OSError, ValueError):
                    best = None
                result.append((spec, best))
    return result
