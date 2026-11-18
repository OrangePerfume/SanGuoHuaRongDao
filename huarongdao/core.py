"""华容道游戏规则与最短单格路径搜索（不依赖 GUI）。"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

BOARD_W, BOARD_H = 4, 5
GOAL = 3 * BOARD_W + 1


@dataclass(frozen=True)
class Piece:
    name: str
    w: int
    h: int
    initial: int


# 顺序与搜索的同型棋子分组保持一致，不能在没有同步调整 canonical() 的情况下改变。
PIECES: tuple[Piece, ...] = (
    Piece("曹操", 2, 2, 1),
    Piece("关羽", 2, 1, 9),
    Piece("张飞", 1, 2, 0),
    Piece("赵云", 1, 2, 3),
    Piece("马超", 1, 2, 8),
    Piece("黄忠", 1, 2, 11),
    Piece("卒", 1, 1, 13),
    Piece("卒", 1, 1, 14),
    Piece("卒", 1, 1, 16),
    Piece("卒", 1, 1, 19),
)
START: tuple[int, ...] = tuple(p.initial for p in PIECES)


@dataclass(frozen=True)
class SolverMove:
    w: int
    h: int
    source: int
    target: int


def mask(w: int, h: int, pos: int) -> int:
    x, y = pos % BOARD_W, pos // BOARD_W
    return sum(1 << ((y + dy) * BOARD_W + (x + dx))
               for dy in range(h) for dx in range(w))


def valid(positions: tuple[int, ...]) -> bool:
    if len(positions) != len(PIECES):
        return False
    occupied = 0
    for p, pos in zip(PIECES, positions):
        if not isinstance(pos, int):
            return False
        x, y = pos % BOARD_W, pos // BOARD_W
        if pos < 0 or x + p.w > BOARD_W or y + p.h > BOARD_H:
            return False
        current = mask(p.w, p.h, pos)
        if occupied & current:
            return False
        occupied |= current
    return True


def won(positions: tuple[int, ...]) -> bool:
    return positions[0] == GOAL


def occupied_by(positions: tuple[int, ...], x: int, y: int) -> int | None:
    if not (0 <= x < BOARD_W and 0 <= y < BOARD_H):
        return None
    for i, (p, pos) in enumerate(zip(PIECES, positions)):
        px, py = pos % BOARD_W, pos // BOARD_W
        if px <= x < px + p.w and py <= y < py + p.h:
            return i
    return None


def shifted(positions: tuple[int, ...], index: int, dx: int, dy: int,
            amount: int = 1) -> tuple[int, ...] | None:
    """返回合法的移动后状态，否则 None。多格移动须逐格可达。"""
    if not isinstance(index, int) or not (0 <= index < len(PIECES)):
        return None
    if (abs(dx) + abs(dy)) != 1 or not isinstance(amount, int) or amount < 1:
        return None
    p = PIECES[index]
    old = positions[index]
    others = 0
    for i, (other, pos) in enumerate(zip(PIECES, positions)):
        if i != index:
            others |= mask(other.w, other.h, pos)
    x, y = old % BOARD_W, old // BOARD_W
    for step in range(1, amount + 1):
        nx, ny = x + dx * step, y + dy * step
        if nx < 0 or ny < 0 or nx + p.w > BOARD_W or ny + p.h > BOARD_H:
            return None
        if mask(p.w, p.h, ny * BOARD_W + nx) & others:
            return None
    result = list(positions)
    result[index] = (y + dy * amount) * BOARD_W + (x + dx * amount)
    return tuple(result)


def canonical(positions: tuple[int, ...]) -> tuple[int, ...]:
    """同尺寸棋子不可区分；消去标号带来的等价状态。"""
    return (positions[0], positions[1], *sorted(positions[2:6]),
            *sorted(positions[6:10]))


# 预计算合法棋子落点及向四周移动一格的几何相邻关系。
_MASKS: dict[tuple[int, int, int], int] = {}
_NEIGHBORS: dict[tuple[int, int, int], tuple[int, ...]] = {}
for _w, _h in {(piece.w, piece.h) for piece in PIECES}:
    for _y in range(BOARD_H - _h + 1):
        for _x in range(BOARD_W - _w + 1):
            _pos = _y * BOARD_W + _x
            _MASKS[_w, _h, _pos] = mask(_w, _h, _pos)
            _NEIGHBORS[_w, _h, _pos] = tuple(
                ny * BOARD_W + nx
                for nx, ny in ((_x - 1, _y), (_x + 1, _y),
                               (_x, _y - 1), (_x, _y + 1))
                if 0 <= nx <= BOARD_W - _w and 0 <= ny <= BOARD_H - _h
            )


def shortest_path(positions: tuple[int, ...]) -> list[SolverMove] | None:
    """广度优先搜索最少单格滑动路径。返回动作序列；不可达返回 None。"""
    if not valid(positions):
        raise ValueError("非法的华容道棋局")
    start = canonical(positions)
    if won(start):
        return []
    queue = deque([start])
    visited = {start}
    parents: dict[tuple[int, ...], tuple[tuple[int, ...], SolverMove]] = {}
    while queue:
        state = queue.popleft()
        current_masks = [_MASKS[p.w, p.h, pos]
                         for p, pos in zip(PIECES, state)]
        occupied = 0
        for piece_mask in current_masks:
            occupied |= piece_mask
        for i, pos in enumerate(state):
            piece = PIECES[i]
            others = occupied ^ current_masks[i]
            for target in _NEIGHBORS[piece.w, piece.h, pos]:
                if _MASKS[piece.w, piece.h, target] & others:
                    continue
                changed = list(state)
                changed[i] = target
                next_state = canonical(tuple(changed))
                if next_state in visited:
                    continue
                visited.add(next_state)
                parents[next_state] = (
                    state, SolverMove(piece.w, piece.h, pos, target))
                if won(next_state):
                    answer: list[SolverMove] = []
                    cursor = next_state
                    while cursor != start:
                        prev, move = parents[cursor]
                        answer.append(move)
                        cursor = prev
                    answer.reverse()
                    return answer
                queue.append(next_state)
    return None


def index_for_solver_move(positions: tuple[int, ...], move: SolverMove) -> int:
    """将求解器等价棋子动作映射回带历史人物名称的实际棋子。"""
    for i, (p, pos) in enumerate(zip(PIECES, positions)):
        if p.w == move.w and p.h == move.h and pos == move.source:
            return i
    raise ValueError("无法找到最短路径中的棋子")
