[简体中文](../../CHANGELOG.md) · [繁體中文](../../docs/zh-TW/CHANGELOG.md) · [English](../../docs/en/CHANGELOG.md)

# Changelog

## V0.6.0 — 2026-11-26

- Added a Next move button that recommends one legal single-cell slide using the existing shortest-path solver, without moving pieces automatically.
- Highlighted the recommended piece with a gold outline and explained its location and direction in the footer, independently of the green destination hints.
- Added manual hint clearing and invalidated stale hints after board changes, undo, pause, or restart.
- Localized hints in Simplified Chinese, Traditional Chinese, and English while preserving puzzle state and move counts during language changes.
- Added regression tests for hint legality, puzzle state, three-language display, and window layout.

## V0.5.0 — 2026-11-26

- Fixed hit testing during piece animations by sharing visual geometry with rendering and preserving clickable piece margins (PR #5).
- Checked both visual and logical vacancy during animation to prevent unintended movement on mouse release.
- Fixed potential duplicate completion notifications after rapid undo and re-completion; notifications wait for animation completion and are canceled on undo, restart, or window closure.
- Fixed keyboard focus trapping on the board: Q / E select pieces, Tab / Shift+Tab navigate controls, and arrows / WASD still move pieces.
- Added regression tests for completion notifications, animation speed, consecutive dragging, multi-selection, undo, and keyboard focus navigation.

## V0.4.0 — 2026-11-25

- Fixed horizontal overflow in the English sidebar at smaller window sizes and improved wrapping and sidebar width adaptation across all three languages.
- Added a language-switching button in the upper-right corner: Simplified Chinese, Traditional Chinese, and English, updated immediately.
- Localized board labels, character names, controls, records, timers, help text, speed settings, and confirmation dialogs.
- Saved the chosen UI language across launches; switching languages preserves the puzzle, undo history, timer, and animation speed.
- Preserved full-shape destination hints and responsive layout, with improved fitting of longer English character names on piece labels.
- Added regression checks for translation coverage, formatting arguments, persistence, and window geometry.
- Merged overlapping destination outlines in the same direction into one uniformly filled rectangle while preserving legal movement distances.
- Switched Windows distribution to a single-file EXE with a ZIP containing only the executable, README.md and combined LICENSE.txt.

## V0.3.0 — 2026-11-21

- Improved fast consecutive moves: animations continue from the current on-screen position rather than restarting from an outdated cell.
- Added smooth visual undo for single pieces and grouped moves, including during ongoing animations.
- Added persistent Slow, Normal, and Fast animation speed choices in the right-hand panel.
- Reported measured sizes of the EXE, application folder, and Windows release ZIP during local builds and GitHub Actions.
- Improved automated GitHub Releases: preserve a downloadable Windows build artifact; update assets when the version Release already exists.
- Added regression tests for animation continuity, undo, speed presets, and build-size measurement.

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

