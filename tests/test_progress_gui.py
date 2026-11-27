"""Integration tests for persisted games, statistics UI, and translations."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from huarongdao.i18n import LANGUAGES, tr
from huarongdao.progress import Profile


class ProgressTranslationTests(unittest.TestCase):
    def test_statistic_translations(self):
        row = Profile().stats['classic']
        for language, _ in LANGUAGES:
            self.assertIn('0', tr(language, 'stats_counts', **row))
            for key in ('stats_title', 'save_ready', 'save_restored', 'save_error', 'save_invalid', 'save_locked'):
                self.assertTrue(tr(language, key))


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'Requires PySide6 / Qt')
class ProgressGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_restart_app_resume_and_switch_puzzle(self):
        from huarongdao.gui import MainWindow
        with TemporaryDirectory() as td:
            first = MainWindow()
            second = None
            try:
                first.enable_progress(Path(td))
                first.select_puzzle('first_arrival')
                first._request_hint()
                hint = first.board.solution_hint
                first._make_move(hint.piece, hint.dx, hint.dy, 1)
                expected = first.game.positions
                first.close()
                second = MainWindow()
                second.enable_progress(Path(td))
                self.assertEqual(second.game.positions, expected)
                self.assertEqual(second.game.steps, 1)
                self.assertEqual(second.game.hint_count, 1)
                self.assertTrue(second.game.paused)
                self.assertEqual(second.profile.stats['first_arrival']['moves'], 1)
                self.assertEqual(second.profile.stats['first_arrival']['hints'], 1)
                self.assertIsNone(second.board.solution_hint)
                second._pause()
                self.assertFalse(second.game.paused)
                second._undo()
                self.assertEqual(second.profile.stats['first_arrival']['undos'], 1)
                self.assertTrue(second.select_puzzle('classic'))
                for language, _ in LANGUAGES:
                    second.set_language(language, persist=False)
                    second.show()
                    second.resize(990, 700)
                    self.app.processEvents()
                    self.assertEqual(second.stats_button.text(), tr(language, 'stats_title'))
                    self.assertEqual(second.side_scroll.horizontalScrollBar().maximum(), 0)
                    self.assertGreaterEqual(second.stats_button.width(), second.stats_button.minimumSizeHint().width())
                    self.assertGreaterEqual(second.save_status.height() + 2,
                                            second.save_status.heightForWidth(second.save_status.width()))
                with patch.object(second, '_exec_preferences_dialog', return_value=0) as open_dialog:
                    second._open_statistics()
                    open_dialog.assert_called_once()
            finally:
                if second is not None:
                    second.close()
                # Do not close a previously closed persistent window a second time.
                if first._progress_timer is None or first._progress_timer.isActive():
                    first.close()

    def test_invalid_save_is_not_overwritten(self):
        from huarongdao.gui import MainWindow
        with TemporaryDirectory() as td:
            path = Path(td) / 'progress.json'
            path.write_bytes(b'corrupt')
            win = MainWindow()
            try:
                win.enable_progress(Path(td))
                self.assertIsNone(win.progress_store)
                self.assertEqual(win._progress_state, 'save_invalid')
                win._make_move(8, 1, 0, 1)
            finally:
                win.close()
            self.assertEqual(path.read_bytes(), b'corrupt')

    def test_second_window_cannot_overwrite_first_window_save(self):
        from huarongdao.gui import MainWindow
        with TemporaryDirectory() as td:
            root = Path(td)
            first, second = MainWindow(), MainWindow()
            try:
                first.enable_progress(root)
                first._make_move(8, 1, 0, 1)
                original = (root / 'progress.json').read_bytes()
                second.enable_progress(root)
                self.assertEqual(second._progress_state, 'save_locked')
                self.assertFalse(second._records_writable)
                second._make_move(9, -1, 0, 1)
                second.close()
                self.assertEqual((root / 'progress.json').read_bytes(), original)
                first.close()
                self.assertFalse((root / 'progress.lock').exists())
            finally:
                first.close()
                second.close()
