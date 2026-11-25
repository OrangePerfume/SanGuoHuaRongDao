"""Single-file packaging uses an explicit three-file manifest."""
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import unittest

from huarongdao import __version__
from tools.package_windows import NAMES, package

ROOT = Path(__file__).resolve().parents[1]


class WindowsPackageTests(unittest.TestCase):
    def test_zip_contains_only_exe_readme_and_license(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            exe = root / 'game.exe'
            exe.write_bytes(b'MZ sample executable')
            (root / '_internal').mkdir()
            (root / 'CHANGELOG.md').write_text('not for distribution')
            archive = root / 'release.zip'
            package(exe, root / 'stage', archive, f'v{__version__}', 'MIT and LGPL notices')
            with ZipFile(archive) as z:
                self.assertEqual(tuple(z.namelist()), NAMES)
                self.assertEqual(z.read(NAMES[0]), exe.read_bytes())
                self.assertIn(b'LGPL', z.read(NAMES[2]))
                self.assertIn(b'OrangePerfume', z.read(NAMES[1]))
                self.assertIsNone(z.testzip())

    def test_rejects_missing_exe_bad_tag_and_dirty_stage(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            exe = root / 'game.exe'
            stage = root / 'stage'
            archive = root / 'release.zip'
            tag = f'v{__version__}'
            with self.assertRaises(FileNotFoundError):
                package(exe, stage, archive, tag, 'notice')
            exe.write_bytes(b'MZ')
            with self.assertRaises(ValueError):
                package(exe, stage, archive, 'v0.0.0', 'notice')
            stage.mkdir()
            (stage / '_internal').mkdir()
            with self.assertRaises(ValueError):
                package(exe, stage, archive, tag, 'notice')
            self.assertFalse(archive.exists())

    def test_ci_and_local_build_share_onefile_packaging(self):
        for path in ('build.cmd', '.github/workflows/release.yml'):
            source = (ROOT / path).read_text(encoding='utf-8')
            self.assertIn('--onefile', source)
            self.assertNotIn('--onedir', source)
            self.assertIn('tools/package_windows.py', source)
            self.assertIn('tools/check_frozen.py', source)
            self.assertLess(source.index('tools/check_frozen.py'), source.index('tools/package_windows.py'))
            self.assertIn('tools/run_tests.py --require-qt', source)
        for license_name in ('GPL-3.txt', 'LGPL-3.txt'):
            self.assertGreater((ROOT / 'tools/licenses' / license_name).stat().st_size, 5000)
