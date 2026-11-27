"""本地最佳成绩记录；异常时不影响游戏主流程。"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from .puzzles import DEFAULT_PUZZLE, PUZZLES


# A legitimate score contains only two small integers. Limit untrusted local
# file reads before decoding or parsing, and reject unrealistic integer sizes.
MAX_RECORD_BYTES = 4096
MAX_RECORD_VALUE = (1 << 63) - 1


def _valid_score(steps: object, seconds: object) -> bool:
    return (type(steps) is int and 1 <= steps <= MAX_RECORD_VALUE
            and type(seconds) is int and 0 <= seconds <= MAX_RECORD_VALUE)


class RecordStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    @classmethod
    def for_puzzle(cls, directory: Path, puzzle_id: str) -> RecordStore:
        if puzzle_id not in PUZZLES:
            raise ValueError("Unknown puzzle")
        # Preserve the original classic score without migration or overwriting it.
        filename = 'best.json' if puzzle_id == DEFAULT_PUZZLE else f'best-{puzzle_id}.json'
        return cls(Path(directory) / filename)

    def load(self) -> dict[str, int]:
        try:
            with self.path.open('rb') as source:
                raw = source.read(MAX_RECORD_BYTES + 1)
            if len(raw) > MAX_RECORD_BYTES:
                return {}
            data = json.loads(raw.decode('utf-8'))
            if isinstance(data, dict) and _valid_score(data.get('steps'), data.get('seconds')):
                return {"steps": data["steps"], "seconds": data["seconds"]}
        except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
            pass
        return {}

    def update_best(self, steps: int, seconds: int) -> bool:
        if not _valid_score(steps, seconds):
            raise ValueError("非法成绩")
        old = self.load()
        if old and (steps, seconds) >= (old["steps"], old["seconds"]):
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        target = self.path
        tmp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=target.parent,
                prefix=".record-", suffix=".tmp", delete=False,
            ) as f:
                tmp_path = f.name
                json.dump({"steps": steps, "seconds": seconds}, f, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, target)
        finally:
            if tmp_path is not None:
                try:
                    Path(tmp_path).unlink(missing_ok=True)
                except OSError:
                    pass
        return True
