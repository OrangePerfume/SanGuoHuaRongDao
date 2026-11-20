[简体中文](../../README.md) · [繁體中文](../../docs/zh-TW/README.md) · [English](../../docs/en/README.md)

# Three Kingdoms Klotski — Heng Dao Li Ma (V0.2.0)

[![Windows CI](https://github.com/OrangePerfume/SanGuoHuaRongDao/actions/workflows/ci.yml/badge.svg)](https://github.com/OrangePerfume/SanGuoHuaRongDao/actions/workflows/ci.yml) [![MIT License](https://img.shields.io/badge/license-MIT-yellow.svg)](../../LICENSE)

A fully offline sliding-block puzzle for **Windows 10 / 11**, featuring the classic *Heng Dao Li Ma* layout, a richly colored wooden board, and Three Kingdoms character illustrations. It brings back the **gameplay**, not the monochrome display.

**Version: 0.2.0.** This version builds on V0.1.0 with click-to-move and group movement.

![Static preview assembled from project artwork, not a running Windows screenshot](../../PREVIEW.png)

> This is an artwork-based static preview, not a Windows runtime screenshot. The game UI itself currently remains in Simplified Chinese; these are **English project documents**.

## Rules

- The board has **4 columns × 5 rows**, 10 pieces, and two empty cells.
- Cao Cao occupies **2×2**; Guan Yu **2×1**; four vertical generals each **1×2**; four soldiers each **1×1**.
- Pieces slide horizontally or vertically only. Rotation, overlap, jumping over pieces, and moving outside the board are not allowed.
- Win by moving Cao Cao to the **bottom-center exit**.

## Controls

- **Mouse drag**: Hold a piece and drag it horizontally or vertically. Every intermediate cell must remain legal.
- **Keyboard**: Select a piece, then use the arrow keys or WASD to move one cell at a time.
- **Shortcuts**: Ctrl+Z to undo, R to restart, Space to pause or resume.
- **Steps and timer**: Each piece moving one cell counts as one step; the timer starts on the first valid move. Best results are saved locally after a win.
- **Click-to-move**: Select a piece, then click an available green destination cell. It moves along a legal straight path, clearing the selection and hint after a successful mouse move.
- **Ctrl multi-selection**: Hold Ctrl while selecting additional pieces. The group can move in the same direction by the same distance; any collision or out-of-bounds movement rejects the operation.
- **Full-shape destination hints**: Cao Cao has one 2×2 square hint; the horizontal general has a 2×1 rectangle; vertical generals have 1×2 rectangles; soldiers have 1×1 squares. Hints are not broken into per-cell boxes.
- **Group undo**: One synchronized movement is undone as a single action; the step count remains the number of pieces times the number of cells moved.

- **Help panel layout**: The right-side instructions are grouped and wrap automatically; scroll within the panel to read everything in a smaller window.

## Download and run

Download the version-matched `SanGuoHuaRongDao-v0.2.0-win-x64.zip` from [GitHub Releases](https://github.com/OrangePerfume/SanGuoHuaRongDao/releases) (available only after a successful build and publication). Extract the entire ZIP, then run:

`SanGuoHuaRongDao/SanGuoHuaRongDao.exe`

Keep all files in the application directory; do not copy only the EXE. The running game does not require an internet connection.

## Running from source / building for Windows

Python 3.12 x64 is recommended:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

Run `build.cmd` from the repository root to install build dependencies, execute the tests, and produce `dist\SanGuoHuaRongDao\SanGuoHuaRongDao.exe`. Installing dependencies for the first time requires network access.

## Project layout and verification

| Path | Purpose |
| --- | --- |
| `huarongdao/core.py` | Board rules, collisions, and the puzzle solver |
| `huarongdao/model.py` | Game session, undo, timing, and move counting |
| `huarongdao/gui.py` | PySide6 / Qt user interface |
| `huarongdao/records.py` | Local best-result storage |
| `huarongdao/assets/` | Character art, wooden textures, and icons |
| `tests/` | Rules, assets, GUI smoke tests, and documentation checks |
| `.github/workflows/` | Windows CI and tag-triggered releases |

Test command: `python -m unittest discover -s tests -v`. CI installs Qt and runs on Windows. Passing non-Qt tests alone does not constitute a completed Windows GUI verification.

## License and more information

The project uses the [MIT License](../../LICENSE). See [Third-party notices](THIRD_PARTY_NOTICES.md) for Qt/PySide6 and other dependency obligations. Character artwork was made for this project with AI assistance; no existing movie, television, or game screenshots are included.

[Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Third-party notices](THIRD_PARTY_NOTICES.md) · [Releases](https://github.com/OrangePerfume/SanGuoHuaRongDao/releases)
