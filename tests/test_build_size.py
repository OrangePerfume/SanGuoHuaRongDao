"""Build size inspection uses actual disk sizes and fails on missing outputs."""
import tempfile
from pathlib import Path
import unittest

from tools.report_build_size import size_report


class BuildSizeTests(unittest.TestCase):
    def test_measures_uncompressed_directory_exe_and_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'app'
            folder.mkdir()
            executable = folder / 'game.exe'
            executable.write_bytes(b'a' * 7)
            (folder / 'module.dll').write_bytes(b'b' * 13)
            archive = root / 'package.zip'
            archive.write_bytes(b'c' * 5)
            self.assertEqual(size_report(folder, executable, archive),
                             {'exe': 7, 'directory': 20, 'zip': 5})

    def test_windows_build_and_release_both_report_sizes(self):
        root = Path(__file__).resolve().parents[1]
        for filename in (root / 'build.cmd', root / '.github/workflows/release.yml'):
            with self.subTest(file=filename.name):
                self.assertIn('tools/report_build_size.py', filename.read_text(encoding='utf-8'))

    def test_missing_build_fails_loudly(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(FileNotFoundError):
                size_report(root / 'missing', root / 'missing.exe')


if __name__ == '__main__':
    unittest.main()
