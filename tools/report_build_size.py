"""Display measured Windows build sizes; no guesswork or dependency trimming."""
from __future__ import annotations

import argparse
from pathlib import Path


def size_report(folder: Path, executable: Path, archive: Path | None = None) -> dict[str, int]:
    if not folder.is_dir() or not executable.is_file():
        raise FileNotFoundError(f"Build output missing: {folder} / {executable}")
    results = {
        "exe": executable.stat().st_size,
        "directory": sum(item.stat().st_size for item in folder.rglob('*') if item.is_file()),
    }
    if archive is not None:
        if not archive.is_file():
            raise FileNotFoundError(f"Archive missing: {archive}")
        results["zip"] = archive.stat().st_size
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dir', required=True, type=Path)
    parser.add_argument('--exe', required=True, type=Path)
    parser.add_argument('--zip', type=Path)
    options = parser.parse_args()
    print('Windows build sizes (measured):')
    for key, value in size_report(options.dir, options.exe, options.zip).items():
        print(f'  {key}: {value:,} bytes ({value / 1024 / 1024:.2f} MiB)')


if __name__ == '__main__':
    main()
