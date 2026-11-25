"""Create the three-file Windows distribution without copying build leftovers."""
from __future__ import annotations

import argparse
from importlib import metadata
from pathlib import Path
import shutil
import sys
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from huarongdao import __version__

NAMES = ('SanGuoHuaRongDao.exe', 'README.md', 'LICENSE.txt')
REPOSITORY = 'https://github.com/OrangePerfume/SanGuoHuaRongDao'


def readme(tag: str) -> str:
    source = f'{REPOSITORY}/tree/{tag}'
    return f'''# 三国华容道 / 三國華容道 / Three Kingdoms Huarong Dao {tag}

Windows 10 / 11 x64

## 简体中文
解压后双击 `SanGuoHuaRongDao.exe` 即可离线游戏，无需安装 Python 或 Qt。
右上角可切换语言。保留 LICENSE.txt（包含项目与第三方许可声明）。

## 繁體中文
解壓縮後雙擊 `SanGuoHuaRongDao.exe` 即可離線遊戲，無須安裝 Python 或 Qt。
右上角可切換語言。請保留 LICENSE.txt（包含專案與第三方授權聲明）。

## English
Extract and run `SanGuoHuaRongDao.exe`. No separate Python or Qt installation is required.
Use the upper-right language button. Retain LICENSE.txt for project and third-party notices.

## Documentation / 文件 / 文档
- [简体中文]({source}/README.md)
- [繁體中文]({source}/docs/zh-TW/README.md)
- [English]({source}/docs/en/README.md)
- [Source / 原始碼 / 源码]({source})
- [Third-party notices]({source}/THIRD_PARTY_NOTICES.md)

## Qt / LGPL
This application uses Qt for Python (PySide6). The LGPL allows users to modify
and relink the covered libraries and run the modified application. The project
source and build scripts are available at the version link above. To rebuild
with a compatible modified PySide6/Qt, install those libraries in a Python 3.12
x64 virtual environment, install PyInstaller and the build requirements, then
run the PyInstaller command in build.cmd with that environment (without
reinstalling the original pinned Qt wheels). Source execution with `python main.py`
is also supported. The publisher must make the corresponding library source
and any required build information available under the applicable terms.
Source and licensing enquiries: {REPOSITORY}/issues
'''


def license_text(tag: str) -> str:
    chunks = [(ROOT / 'LICENSE').read_text(encoding='utf-8'),
              'Third-party notices / 第三方许可 / 第三方授權',
              (ROOT / 'THIRD_PARTY_NOTICES.md').read_text(encoding='utf-8'),
              f'Version source: {REPOSITORY}/tree/{tag}',
              'Qt/PySide6: LGPLv3/GPLv3 as applicable. The following license texts do not change the project MIT license.']
    for name in ('GPL-3', 'LGPL-3'):
        chunks.append((ROOT / 'tools' / 'licenses' / (name + '.txt')).read_text(encoding='utf-8'))
    python_license = next((p for p in (Path(sys.base_prefix)/'LICENSE.txt', Path(sys.base_prefix)/'LICENSE') if p.is_file()), None)
    if python_license is None:
        raise FileNotFoundError('Python runtime license is missing from the Windows Python installation')
    chunks.extend([f'Python {sys.version.split()[0]}', python_license.read_text(encoding='utf-8', errors='replace')])
    # Retain installed wheel notices, including licenses nested inside dist-info/licenses.
    for name in ('PySide6', 'PySide6-Essentials', 'PySide6-Addons', 'shiboken6', 'PyInstaller'):
        dist = metadata.distribution(name)
        chunks.append(f'\n{name} {dist.version} — distribution notices\n')
        if dist.metadata.get('License'):
            chunks.append(dist.metadata['License'])
        for f in sorted(dist.files or (), key=str):
            parts = [part.lower() for part in f.parts]
            base = f.name.lower()
            if ('licenses' not in parts and not base.startswith(('license', 'copying', 'notice', 'copyright', 'third_party', 'third-party'))):
                continue
            if f.suffix.lower() not in ('', '.txt', '.md', '.rst', '.html', '.htm'):
                continue
            path = Path(dist.locate_file(f))
            if path.is_file():
                chunks.extend([str(f), path.read_text(encoding='utf-8', errors='replace')])
    return '\n\n'.join(chunks) + '\n'


def package(executable: Path, stage: Path, archive: Path, tag: str, notices: str) -> None:
    if tag != f'v{__version__}':
        raise ValueError(f'Tag {tag} does not match version v{__version__}')
    if not executable.is_file() or executable.stat().st_size == 0:
        raise FileNotFoundError(f'Executable missing or empty: {executable}')
    stage.mkdir(parents=True, exist_ok=True)
    # A reused stage must not introduce old files or silently delete unrelated data.
    if set(p.name for p in stage.iterdir()) - set(NAMES):
        raise ValueError('Unexpected files in the release staging directory')
    shutil.copyfile(executable, stage / NAMES[0])
    (stage / NAMES[1]).write_text(readme(tag), encoding='utf-8')
    (stage / NAMES[2]).write_text(notices, encoding='utf-8')
    archive.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive, 'w', ZIP_DEFLATED) as z:
        for name in NAMES:
            z.write(stage / name, name)
    with ZipFile(archive) as z:
        if tuple(z.namelist()) != NAMES or z.testzip() is not None:
            raise RuntimeError('Invalid Windows ZIP')


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--exe', required=True, type=Path)
    p.add_argument('--stage', required=True, type=Path)
    p.add_argument('--zip-dir', required=True, type=Path)
    p.add_argument('--tag', default=f'v{__version__}')
    args = p.parse_args()
    archive = args.zip_dir / f'SanGuoHuaRongDao-{args.tag}-win-x64.zip'
    package(args.exe, args.stage, archive, args.tag, license_text(args.tag))
    print(f'Windows ZIP: {archive} ({archive.stat().st_size:,} bytes)')


if __name__ == '__main__':
    main()
