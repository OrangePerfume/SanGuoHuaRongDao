"""Render-only motion interpolation; the puzzle model remains the source of truth.

Coordinates are measured in logical board cells, so window resizing/high DPI
scaling does not change animation paths.  No Qt dependency is required.
"""
from __future__ import annotations

from dataclasses import dataclass, field

BOARD_WIDTH = 4
ANIMATION_DURATIONS_MS = {"slow": 260, "normal": 155, "fast": 90}


def cell(position: int) -> tuple[float, float]:
    return float(position % BOARD_WIDTH), float(position // BOARD_WIDTH)


@dataclass
class MotionTrack:
    starts: dict[int, tuple[float, float]] = field(default_factory=dict)
    targets: dict[int, tuple[float, float]] = field(default_factory=dict)
    progress: float = 1.0

    def displayed(self, index: int, positions: tuple[int, ...]) -> tuple[float, float]:
        if index not in self.starts:
            return cell(positions[index])
        start = self.starts[index]
        target = self.targets[index]
        t = max(0.0, min(1.0, self.progress))
        return start[0] + (target[0] - start[0]) * t, start[1] + (target[1] - start[1]) * t

    def retarget(self, before: dict[int, int], positions: tuple[int, ...]) -> bool:
        """Retarget while keeping the exact positions currently drawn on screen.

        `before` contains positions *before the latest successful move/undo*.
        Previous targets are stored separately from the now-updated game model.
        """
        starts: dict[int, tuple[float, float]] = {}
        targets: dict[int, tuple[float, float]] = {}
        for index in set(before) | set(self.starts):
            if index < 0 or index >= len(positions):
                raise ValueError(f"invalid piece index: {index}")
            origin = (self.displayed(index, positions) if index in self.starts
                      else cell(before.get(index, positions[index])))
            target = cell(positions[index])
            if abs(origin[0] - target[0]) > 1e-9 or abs(origin[1] - target[1]) > 1e-9:
                starts[index] = origin
                targets[index] = target
        self.starts, self.targets = starts, targets
        self.progress = 0.0 if starts else 1.0
        return bool(starts)

    def set_progress(self, value: float) -> None:
        self.progress = max(0.0, min(1.0, float(value)))

    def complete(self) -> None:
        self.starts.clear()
        self.targets.clear()
        self.progress = 1.0
