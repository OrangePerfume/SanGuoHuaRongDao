"""无 GUI 依赖的游戏会话模型：计步、撤销、暂停和通关。"""
from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Callable

from .core import START, shifted, valid, won


@dataclass
class GameModel:
    clock: Callable[[], float] = time.monotonic
    positions: tuple[int, ...] = START
    history: list[tuple[int, ...]] = field(default_factory=list)
    steps: int = 0
    paused: bool = False
    _elapsed: float = 0.0
    _running_since: float | None = None

    @property
    def finished(self) -> bool:
        return won(self.positions)

    @property
    def running(self) -> bool:
        return self._running_since is not None

    @property
    def elapsed(self) -> float:
        if self._running_since is None:
            return self._elapsed
        return self._elapsed + max(0.0, self.clock() - self._running_since)

    def reset(self) -> None:
        self.positions = START
        self.history.clear()
        self.steps = 0
        self.paused = False
        self._elapsed = 0.0
        self._running_since = None

    def move(self, piece_index: int, dx: int, dy: int, count: int = 1) -> int:
        """沿单轴移动至多 count 格；每移动一格计一步，支持逐格撤销。"""
        if self.paused or self.finished or not isinstance(count, int) or count < 1:
            return 0
        moved = 0
        for _ in range(count):
            after = shifted(self.positions, piece_index, dx, dy)
            if after is None:
                break
            if self._running_since is None:
                self._running_since = self.clock()
            self.history.append(self.positions)
            self.positions = after
            self.steps += 1
            moved += 1
            if self.finished:
                self._freeze_time()
                break
        return moved

    def undo(self) -> bool:
        if not self.history or self.paused:
            return False
        self.positions = self.history.pop()
        self.steps -= 1
        if self._running_since is None and self.steps > 0:
            self._running_since = self.clock()
        if self.steps == 0:
            self._elapsed = 0.0
            self._running_since = None
        return True

    def _freeze_time(self) -> None:
        if self._running_since is not None:
            self._elapsed += max(0.0, self.clock() - self._running_since)
            self._running_since = None

    def toggle_pause(self) -> bool:
        if self.finished or not self.running and not self.paused:
            # 游戏尚未开始时无需暂停。
            return self.paused
        if self.paused:
            self.paused = False
            self._running_since = self.clock()
        else:
            self._freeze_time()
            self.paused = True
        return self.paused

    def replace_for_test(self, positions: tuple[int, ...]) -> None:
        """仅用于测试加载布局的规则检查，不用于读取外部存档。"""
        if not valid(positions):
            raise ValueError("棋局无效")
        self.positions = positions
        self.history.clear()
        self.steps = 0
        self.paused = False
        self._elapsed = 0
        self._running_since = None
