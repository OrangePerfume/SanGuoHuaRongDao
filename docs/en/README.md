[简体中文](../../README.md) · [繁體中文](../../docs/zh-TW/README.md) · [English](../../docs/en/README.md)

# Three Kingdoms Klotski (V0.10.0)

[![Windows CI](https://github.com/OrangePerfume/SanGuoHuaRongDao/actions/workflows/ci.yml/badge.svg)](https://github.com/OrangePerfume/SanGuoHuaRongDao/actions/workflows/ci.yml) [![MIT License](https://img.shields.io/badge/license-MIT-yellow.svg)](../../LICENSE)

A fully offline sliding-block puzzle for **Windows 10 / 11**, featuring the classic *Heng Dao Li Ma* layout, a richly colored wooden board, and Three Kingdoms character illustrations. It brings back the **gameplay**, not the monochrome display.

**Version: 0.10.0.** Time and move challenges with four difficulty levels.

Settings controls background dimming, animation speed and language. The selection plaque is beside the board; multi-selection retains full names. The hint card displays recommendations and has a separate clear button. Gameplay instructions can be expanded or collapsed.

![Static preview assembled from project artwork, not a running Windows screenshot](../../PREVIEW.png)

> This is a static preview assembled from project artwork. The game UI and documentation both support Simplified Chinese, Traditional Chinese, and English in one Windows EXE.

## Interface language

- Use the **Language** button in the upper-right corner to choose **简体中文 / 繁體中文 / English**.
- Board labels, character names, controls, help, records, and dialogs change instantly, without restarting the game.
- Simplified Chinese is the default; your last selection is saved. Changing language does not reset the puzzle, undo history, timer, or animation speed.

## Classic puzzles

Use the Puzzle menu to choose Heng Dao Li Ma (116 moves), First to the Goal (47), Side by Side (85), Three Routes (92), The Commander (100), or Encirclement (101). The numbers are shortest paths under the single-piece, single-cell counting rule, not the traditional combined-move count. Heng Dao Li Ma remains the default. Switching confirms discarding current progress; Restart resets only the current puzzle. Each puzzle has its own best score, with the original classic record preserved.

## Saved games and personal records

The current puzzle is saved after moves, undo, pause, hint use, puzzle changes, and exit; elapsed time is checkpointed every five seconds while playing. An unfinished puzzle is restored paused on the next launch. Select Resume game to continue; time spent offline is not counted. Restarting or switching puzzles still requires confirmation and replaces the active save.

Personal records lists earlier best scores for all six puzzles and cumulative completions, unassisted completions, unassisted optimal completions, moves, undos, and hints. The new counters start with this version; earlier best scores are retained. The versioned `progress.json` is stored in the local user data directory. Unreadable files are preserved, and only one window can write a given save.

If saving fails on exit, retry, exit without saving, or cancel. After explicit confirmation, archive an unreadable save in a unique backup folder and start a new record without losing legacy best scores. The personal records dashboard includes fastest completions, total time of recorded completions, distance from the shortest path, manual backups and the data folder. Other windows display saved statistics read-only and do not count local actions.

## Challenge mode

- Add a separate challenge entry for time and move challenges across all six classic puzzles.
- Offer Beginner, Standard, Expert and Extreme limits scaled to each puzzle’s minimum single-cell move count.
- Start the countdown after interface preparation; disable pause, undo and solution hints. Every cell moved per piece counts, including group moves.
- Fail at the time deadline or upon exhausting moves without solving; solving on the final allowed move succeeds.
- Show the outcome and independent best result. Rank time challenges by time first and move challenges by moves first, breaking ties by the other metric.
- Store results by puzzle, mode and difficulty with atomic writes, bounded validation and the existing single-writer lock; preserve invalid files and support retries.
- Active challenges are not resumable and never modify classic saves, undo history or personal statistics. Return to the preserved classic game.
- Add a challenge progress card, low-budget warning and separate result dialog using immutable results, with retry and return actions.
- Add a record overview for all 48 combinations, distinguishing missing and unreadable records.
- Protect classic saves before entering challenges with retry and cancel options; confirm read-only play and archive invalid records only with consent.
- Start timing after interface preparation, constrain group-move previews and distinguish record read and write errors.


## Rules

- The board has **4 columns × 5 rows**, 10 pieces, and two empty cells.
- Cao Cao occupies **2×2**; Guan Yu **2×1**; four vertical generals each **1×2**; four soldiers each **1×1**.
- Pieces slide horizontally or vertically only. Rotation, overlap, jumping over pieces, and moving outside the board are not allowed.
- Win by moving Cao Cao to the **bottom-center exit**.

## Controls

- **Mouse drag**: Hold a piece and drag it horizontally or vertically. Every intermediate cell must remain legal.
- **Keyboard**: Click a piece or select it with Q / E, then use the arrow keys or WASD to move one cell at a time. Tab / Shift+Tab navigate controls.
- **Shortcuts**: Ctrl+Z to undo, R to restart, Space to pause or resume.
- **Steps and timer**: Each piece moving one cell counts as one step; the timer starts on the first valid move. Best results are saved locally after a win.
- **Click-to-move**: Select a piece, then click an available green destination cell. It moves along a legal straight path, clearing the selection and hint after a successful mouse move.
- **Next move**: Click the sidebar button to mark the recommended piece with a gold outline. The hint card shows the direction and top-left grid cell. Hints do not move pieces or increase the move count; use Clear hint to dismiss the recommendation.
- **Ctrl multi-selection**: Hold Ctrl while selecting additional pieces. The group can move in the same direction by the same distance; any collision or out-of-bounds movement rejects the operation.
- **Full-shape destination hints**: Cao Cao has one 2×2 square hint; the horizontal general has a 2×1 rectangle; vertical generals have 1×2 rectangles; soldiers have 1×1 squares. Hints are not broken into per-cell boxes.
- Merged overlapping destination outlines in the same direction into one uniformly filled rectangle while preserving legal movement distances.
- **Group undo**: One synchronized movement is undone as a single action; the step count remains the number of pieces times the number of cells moved.

- **Smooth animation**: Rapid successive moves continue from each piece’s current displayed position; undo also animates back smoothly.
- **Animation speed**: Choose Slow, Normal, or Fast in the right-hand control panel. The preference persists across launches.
- **Help panel layout**: The right-side instructions are grouped and wrap automatically; scroll within the panel to read everything in a smaller window.

## Download and run

Download the version-matched `SanGuoHuaRongDao-v0.10.0-win-x64.zip` from [GitHub Releases](https://github.com/OrangePerfume/SanGuoHuaRongDao/releases). Extract the entire ZIP, then run:

`SanGuoHuaRongDao.exe`

The executable embeds its runtime resources; no separate Python or Qt installation or network access is required. Retain README.md and LICENSE.txt.

Switched Windows distribution to a single-file EXE with a ZIP containing only the executable, README.md and combined LICENSE.txt.

## Running from source / building for Windows

Python 3.12 x64 is recommended:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

Run `build.cmd` from the repository root to install build dependencies, execute the tests, and produce `dist\SanGuoHuaRongDao.exe`. Installing dependencies for the first time requires network access. The build reports measured sizes for the EXE and full distribution folder; the release workflow also measures the ZIP archive.

## Project layout and verification

| Path | Purpose |
| --- | --- |
| `huarongdao/core.py` | Board rules, collisions, and the puzzle solver |
| `huarongdao/model.py` | Game session, undo, timing, and move counting |
| `huarongdao/gui.py` | PySide6 / Qt user interface |
| `huarongdao/i18n.py` | Simplified Chinese, Traditional Chinese, and English UI text |
| `huarongdao/records.py` | Local best-result storage |
| `huarongdao/assets/` | Character art, wooden textures, and icons |
| `tests/` | Rules, assets, GUI smoke tests, and documentation checks |
| `.github/workflows/` | Windows CI and tag-triggered releases |

Strict test command: `python -X faulthandler tools/run_tests.py --require-qt`. Windows CI covers game rules and the Qt interface; failing checks block the build.

Security and quality gates: CodeQL scans Python source, Ruff checks syntax and selected correctness rules, and pip-audit audits dependencies in the actual Windows build environment. Strict Qt tests, executable startup and archive checks also precede publication.

## License and more information

The project uses the [MIT License](../../LICENSE). See [Third-party notices](THIRD_PARTY_NOTICES.md) for Qt/PySide6 and other dependency obligations. Character artwork was made for this project with AI assistance; no existing movie, television, or game screenshots are included.

[Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md) · [Third-party notices](THIRD_PARTY_NOTICES.md) · [Releases](https://github.com/OrangePerfume/SanGuoHuaRongDao/releases)
