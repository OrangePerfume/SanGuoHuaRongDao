"""Fail-closed security gates, release isolation, and malformed score handling."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

from huarongdao.records import MAX_RECORD_BYTES, MAX_RECORD_VALUE, RecordStore

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / '.github' / 'workflows'


class SecurityGateTests(unittest.TestCase):
    def _run_sarif_gate(self, report):
        # Exercise the exact inline gate used for current and historical tags.
        workflow = (WORKFLOWS / 'security.yml').read_text(encoding='utf-8')
        body = workflow.split('<<\'PY\'\n', 1)[1].split('\n          PY', 1)[0]
        code = textwrap.dedent(body)
        with tempfile.TemporaryDirectory() as tmp:
            if report is not None:
                (Path(tmp) / 'python.sarif').write_text(json.dumps(report), encoding='utf-8')
            return subprocess.run([sys.executable, '-c', code, tmp],
                                  capture_output=True, text=True, timeout=15)

    @staticmethod
    def report(results=None, successful=True):
        return {'version': '2.1.0', 'runs': [{'tool': {'driver': {'name': 'CodeQL'}},
                'results': [] if results is None else results,
                'invocations': [{'executionSuccessful': successful}]}]}

    def test_codeql_accepts_only_completed_clean_analysis(self):
        self.assertEqual(self._run_sarif_gate(self.report()).returncode, 0)
        for report in (None, {}, {'version': '2.1.0', 'runs': []},
                       self.report(successful=False), self.report([{'ruleId': 'py/example'}])):
            with self.subTest(report=report):
                self.assertNotEqual(self._run_sarif_gate(report).returncode, 0)
        report = self.report()
        del report['runs'][0]['results']
        self.assertNotEqual(self._run_sarif_gate(report).returncode, 0)

    def test_security_and_quality_are_wired_to_pr_and_release(self):
        ci = (WORKFLOWS / 'ci.yml').read_text(encoding='utf-8')
        release = (WORKFLOWS / 'release.yml').read_text(encoding='utf-8')
        security = (WORKFLOWS / 'security.yml').read_text(encoding='utf-8')
        self.assertIn('pull_request:', ci)
        self.assertNotIn('pull_request_target:', ci + security + release)
        for workflow in (ci, release):
            self.assertIn('uses: ./.github/workflows/security.yml', workflow)
            self.assertIn('python -m pip check', workflow)
            self.assertIn('pip_audit --strict --path $site', workflow)
            self.assertLess(workflow.index('Audit installed dependencies'), workflow.index('tools/run_tests.py --require-qt'))
            self.assertNotIn('continue-on-error: true', workflow)
            self.assertIn('persist-credentials: false', workflow)
        self.assertIn('github/codeql-action/init@v4', security)
        self.assertIn('github/codeql-action/analyze@v4', security)
        self.assertIn('python -m compileall', security)
        self.assertIn('python -m ruff check', security)
        self.assertNotIn('continue-on-error: true', security)
        self.assertIn('needs: [resolve-tag, security]', release)
        self.assertIn('needs: [resolve-tag, build-and-release]', release)
        self.assertIn('checkout_ref: ${{ needs.resolve-tag.outputs.commit }}', release)
        self.assertEqual(release.count('ref: ${{ needs.resolve-tag.outputs.commit }}'), 3)
        before, publish = release.split('  publish-release:', 1)
        self.assertNotIn('contents: write', before)
        self.assertIn('contents: write', publish)
        self.assertIn('Release tag moved after scanning', publish)
        self.assertIn('actions/download-artifact@v4', publish)
        self.assertNotIn('python -m pip install', publish)

    def test_corrupt_and_unreasonably_large_record_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'best.json'
            store = RecordStore(path)
            for raw in (b' ' * (MAX_RECORD_BYTES + 1), b'[' * 1500 + b']' * 1500,
                        b'\xff', json.dumps({'steps': MAX_RECORD_VALUE + 1, 'seconds': 0}).encode(),
                        json.dumps({'steps': 1, 'seconds': MAX_RECORD_VALUE + 1}).encode()):
                with self.subTest(size=len(raw)):
                    path.write_bytes(raw)
                    self.assertEqual(store.load(), {})
            with self.assertRaises(ValueError):
                store.update_best(MAX_RECORD_VALUE + 1, 0)
            self.assertTrue(store.update_best(116, 300))
            self.assertEqual(store.load(), {'steps': 116, 'seconds': 300})
