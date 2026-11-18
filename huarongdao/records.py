"""本地最佳成绩记录；异常时不影响游戏主流程。"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile


class RecordStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def load(self) -> dict[str, int]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if (isinstance(data, dict)
                    and type(data.get("steps")) is int and data["steps"] >= 1
                    and type(data.get("seconds")) is int and data["seconds"] >= 0):
                return {"steps": data["steps"], "seconds": data["seconds"]}
        except (OSError, ValueError, TypeError, UnicodeError):
            pass
        return {}

    def update_best(self, steps: int, seconds: int) -> bool:
        if type(steps) is not int or steps <= 0 or type(seconds) is not int or seconds < 0:
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
