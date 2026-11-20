"""Keep all three documentation languages aligned with the packaged version."""
from pathlib import Path
import re
import unittest
from huarongdao import __version__

ROOT = Path(__file__).resolve().parents[1]

class DocumentationTests(unittest.TestCase):
    def test_all_three_locales_have_project_docs(self):
        names = ("README.md", "CHANGELOG.md", "CONTRIBUTING.md", "THIRD_PARTY_NOTICES.md")
        for name in names:
            for path in (ROOT/name, ROOT/"docs"/"zh-TW"/name, ROOT/"docs"/"en"/name):
                with self.subTest(path=str(path.relative_to(ROOT))):
                    self.assertTrue(path.is_file(), str(path))
                    body=path.read_text(encoding="utf-8")
                    self.assertIn("[简体中文]",body)
                    self.assertIn("[繁體中文]",body)
                    self.assertIn("[English]",body)

    def test_version_and_release_note_consistency(self):
        for path in (ROOT/"README.md", ROOT/"docs"/"zh-TW"/"README.md", ROOT/"docs"/"en"/"README.md"):
            with self.subTest(path=path):
                self.assertIn(__version__,path.read_text(encoding="utf-8"))
        for lang in ("zh-TW", "en"):
            self.assertTrue((ROOT/"docs"/lang/"release-notes"/f"v{__version__}.md").is_file())
        self.assertTrue((ROOT/".github"/"release-notes"/f"v{__version__}.md").is_file())

    def test_no_stale_repository_owner_in_documents(self):
        for p in [ROOT/"README.md", ROOT/"docs"/"zh-TW"/"README.md", ROOT/"docs"/"en"/"README.md"]:
            with self.subTest(path=p):
                self.assertIn("OrangePerfume/SanGuoHuaRongDao", p.read_text(encoding="utf-8"))

    def test_public_license_is_available(self):
        license= (ROOT/"LICENSE").read_text(encoding="utf-8")
        self.assertIn("MIT License",license)
        self.assertIn("OrangePerfume",license)

if __name__ == "__main__":
    unittest.main()
