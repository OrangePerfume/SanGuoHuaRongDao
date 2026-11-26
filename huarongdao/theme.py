"""Geometry and preferences for the Red Cliffs theme, independent of Qt."""
from __future__ import annotations


def normalize_dimming(value: object) -> int:
    try:
        return max(0, min(65, int(value)))
    except (TypeError, ValueError, OverflowError):
        return 22


def board_layout(width: int, height: int, language: str) -> tuple[float, float, float]:
    """Keep the board and its adjacent plaque in the same coordinate system."""
    reserve = 118 if language == 'en' else 86
    unit = max(40.0, min((width - reserve - 70) / 4, (height - 124) / 5))
    return (width - reserve - 4 * unit) / 2, (height - 5 * unit) / 2 + 6, unit


def plaque_geometry(width: int, height: int, language: str) -> tuple[int, int, int, int]:
    x, y, unit = board_layout(width, height, language)
    plaque_width = 104 if language == 'en' else 74
    plaque_height = min(300, max(210, int(5 * unit * .76)))
    return int(x + 4 * unit + 29), int(y + (5 * unit - plaque_height) / 2), plaque_width, plaque_height
