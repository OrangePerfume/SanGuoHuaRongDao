"""An on-demand next-move recommendation; never mutate the puzzle."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from .core import BOARD_W, index_for_solver_move, shortest_path, shifted
from .i18n import piece_name, tr


@dataclass(frozen=True)
class NextMove:
    piece: int
    source: int
    target: int
    dx: int
    dy: int
    remaining: int


@lru_cache(maxsize=128)
def next_move(positions: tuple[int, ...]) -> NextMove | None:
    """Return one legal single-cell move from the shortest path, or None."""
    path = shortest_path(positions)
    if not path:
        return None
    move = path[0]
    index = index_for_solver_move(positions, move)
    dx = move.target % BOARD_W - move.source % BOARD_W
    dy = move.target // BOARD_W - move.source // BOARD_W
    outcome = shifted(positions, index, dx, dy)
    if outcome is None or outcome[index] != move.target:
        raise RuntimeError("Solver returned an illegal recommendation")
    return NextMove(index, move.source, move.target, dx, dy, len(path))


def format_hint(language: str, hint: NextMove | None) -> str:
    if hint is None:
        return tr(language, 'solution_none')
    direction = {(-1, 0): 'left', (1, 0): 'right',
                 (0, -1): 'up', (0, 1): 'down'}[hint.dx, hint.dy]
    return tr(language, 'solution_message', piece=piece_name(language, hint.piece),
              row=hint.source // BOARD_W + 1, col=hint.source % BOARD_W + 1,
              direction=tr(language, 'solution_' + direction))
