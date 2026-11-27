"""Classic one-horizontal-general layouts; stable IDs are also record keys.

Traditional opening positions cross-checked against the public layout catalogue
https://github.com/jeantimex/klotski/blob/master/src/hrd-games.json .
Distances use this project's single-cell, single-piece counting convention.
"""
from dataclasses import dataclass
from types import MappingProxyType
from .core import START


@dataclass(frozen=True)
class Puzzle:
    id: str
    positions: tuple[int, ...]
    minimum_steps: int


DEFAULT_PUZZLE = 'classic'
PUZZLES = MappingProxyType({p.id: p for p in (
    Puzzle('classic', START, 116),
    Puzzle('first_arrival', (1,9,12,13,14,15,0,3,4,7), 47),
    Puzzle('side_by_side', (1,13,0,3,12,15,8,9,10,11), 85),
    Puzzle('three_routes', (1,9,4,7,12,15,0,3,13,14), 92),
    Puzzle('commander', (1,9,0,3,12,15,8,11,13,14), 100),
    Puzzle('encirclement', (1,16,4,7,9,10,12,15,18,19), 101),
)})
