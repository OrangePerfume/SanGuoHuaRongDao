"""Release builds must survive an existing tag/release without bypassing tests."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / '.github/workflows/release.yml'


class ReleaseWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = RELEASE.read_text(encoding='utf-8')

    def test_rebuild_existing_tag_can_be_run_manually(self):
        self.assertIn('workflow_dispatch:', self.content)
        self.assertIn('ref: ${{ inputs.tag || github.ref_name }}', self.content)
        self.assertIn('RELEASE_TAG: ${{ inputs.tag || github.ref_name }}', self.content)

    def test_existing_release_updates_assets_not_tag_or_notes(self):
        self.assertIn('gh release view $tag', self.content)
        self.assertIn('gh release upload $tag $asset --clobber', self.content)
        self.assertIn('gh release create $tag $asset', self.content)
        self.assertNotIn('gh release delete', self.content)
        self.assertNotIn('git push --force', self.content)

    def test_exe_zip_is_saved_before_github_release_upload(self):
        self.assertLess(self.content.index('name: Save Windows ZIP as workflow artifact'),
                        self.content.index('name: Create or update versioned GitHub Release'))
        self.assertIn('actions/upload-artifact@v4', self.content)
        self.assertIn('if-no-files-found: error', self.content)
        self.assertIn('tools/run_tests.py --require-qt', self.content)
        self.assertNotIn('continue-on-error: true', self.content)


if __name__ == '__main__':
    unittest.main()
