[简体中文](../../CHANGELOG.md) · [繁體中文](../../docs/zh-TW/CHANGELOG.md) · [English](../../docs/en/CHANGELOG.md)

# Changelog

## V0.2.0 — 2026-11-20

- Improved the right-side help panel with grouped instructions, automatic wrapping, and an independently scrollable area to prevent clipped text on smaller windows.

- Added selecting a piece and clicking a legal destination cell to slide along an unobstructed straight path.
- Added Ctrl+click multi-selection and synchronized movement by dragging, clicking a destination cell, or pressing direction keys.
- Applied group-level collision and boundary checks with equal direction and distance. Steps remain proportional to pieces × cells; one group operation can be undone together.
- Rendered destination hints using each piece's complete footprint: one 2×2 square for Cao Cao, a 2×1 rectangle for the horizontal general, 1×2 rectangles for vertical generals, and 1×1 squares for soldiers.
- Cleared selection and green hints after successful mouse moves, preserved them after invalid moves, and kept keyboard selection while hiding destination hints.
- Added group movement, hint geometry, and Qt interaction regression tests.

## V0.1.0 — 2026-11-04

- Implemented the classic 4×5 *Heng Dao Li Ma* puzzle, collision and boundary checks, and the win condition.
- Added painted Three Kingdoms characters, a wooden board, and parchment-themed controls.
- Supported single-piece drag movement (including legal multi-cell straight moves), arrow/WASD keys, undo, restart, and pause.
- Started the timer on the first valid move, counted one step per piece per cell, and stored local best scores after a win.
- Included rules, session, record, asset, and basic GUI tests, along with the Windows build script.

> Windows EXE rendering and DPI behavior still require verification in a Windows environment.
