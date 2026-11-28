"""Challenge integration: classic save isolation, shortcut guards and settlement."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from huarongdao.challenge import ChallengeSpec
from huarongdao.challenge_records import ChallengeRecords
from huarongdao.hint import next_move
from huarongdao.core import shortest_path, index_for_solver_move
from huarongdao.i18n import LANGUAGES, tr


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'Requires PySide6 / Qt')
class ChallengeGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_classic_save_isolation_and_shortcut_guards(self):
        from huarongdao.gui import MainWindow
        from huarongdao.progress import ProgressStore
        from huarongdao.model import GameModel
        with TemporaryDirectory() as td:
            root = Path(td)
            win = MainWindow()
            try:
                win.enable_progress(root)
                win._make_move(8, 1, 0, 1)
                classic = win.game
                before = classic.positions
                clock = Clock()
                win._start_challenge(ChallengeSpec('first_arrival', 'time', 'extreme'), clock)
                self.assertIsNot(win.game, classic)
                self.assertTrue(classic.paused)
                hint = next_move(win.game.positions)
                win._make_move(hint.piece, hint.dx, hint.dy, 1)
                self.assertEqual(win.game.steps, 1)
                win._undo()
                win._pause()
                win._request_hint()
                self.assertEqual(win.game.steps, 1)
                self.assertFalse(win.game.paused)
                self.assertEqual(win.game.hint_count, 0)
                self.assertFalse(win.hint_button.isEnabled())
                self.assertFalse(win.undo_button.isEnabled())
                self.assertFalse(win.pause_button.isEnabled())
                self.assertFalse(win.select_puzzle('classic'))
                self.assertTrue(win._save_progress())
                restored = GameModel()
                profile = ProgressStore(root / 'progress.json').load(restored)
                self.assertEqual(restored.positions, before)
                self.assertEqual(profile.stats['classic']['moves'], 1)
                self.assertEqual(profile.stats['first_arrival']['moves'], 0)
                for language, _ in LANGUAGES:
                    win.set_language(language, persist=False)
                    win.resize(990, 700)
                    win.show()
                    self.app.processEvents()
                    self.assertIn(tr(language, 'challenge_time'), win.challenge_status.text())
                    self.assertEqual(win.side_scroll.horizontalScrollBar().maximum(), 0)
                clock.now = win.challenge.spec.limit
                win._update_stats()
                self.assertEqual(win.challenge.status, 'timeout')
                self.assertFalse(win.board.isEnabled())
                self.assertTrue(win._confirm_challenge_leave())
                win._leave_challenge()
                self.assertIs(win.game, classic)
                self.assertTrue(win.board.isEnabled())
                self.assertEqual(win.game.positions, before)
            finally:
                if win.challenge is not None:
                    win._leave_challenge()
                win.close()

    def test_success_record_and_retry(self):
        from huarongdao.gui import MainWindow
        with TemporaryDirectory() as td:
            root = Path(td)
            win = MainWindow()
            try:
                win.enable_progress(root)
                spec = ChallengeSpec('first_arrival', 'steps', 'extreme')
                win._start_challenge(spec, Clock())
                with patch('huarongdao.challenge_records.os.replace', side_effect=OSError('denied')):
                    for move in shortest_path(win.game.positions):
                        index = index_for_solver_move(win.game.positions, move)
                        win._make_move(index, move.target % 4 - move.source % 4, move.target // 4 - move.source // 4, 1)
                self.assertEqual(win.challenge.status, 'success')
                self.assertFalse(win._challenge_saved)
                self.assertTrue(win._challenge_error)
                self.assertFalse(ChallengeRecords(root, spec).path.exists())
                win._retry_challenge_record()
                self.assertTrue(win._challenge_saved)
                self.assertEqual(ChallengeRecords(root, spec).load()['steps'], 47)
                self.assertEqual(win.profile.stats['first_arrival']['wins'], 0)
                win._update_stats()
                self.assertTrue(win._challenge_saved)
                self.assertTrue(win._confirm_challenge_leave())
            finally:
                if win.challenge is not None:
                    win._leave_challenge()
                win.close()

    def test_readonly_window_does_not_write_challenge_records(self):
        from huarongdao.gui import MainWindow
        with TemporaryDirectory() as td:
            root = Path(td)
            first, second = MainWindow(), MainWindow()
            try:
                first.enable_progress(root)
                second.enable_progress(root)
                spec = ChallengeSpec('first_arrival', 'steps', 'extreme')
                with patch.object(second, "_confirm_discard", return_value=True):
                    self.assertTrue(second._start_challenge(spec, Clock()))
                for move in shortest_path(second.game.positions):
                    index = index_for_solver_move(second.game.positions, move)
                    second._make_move(index, move.target % 4 - move.source % 4, move.target // 4 - move.source // 4, 1)
                self.assertEqual(second.challenge.status, 'success')
                self.assertFalse(second._challenge_saved)
                self.assertFalse(ChallengeRecords(root, spec).path.exists())
            finally:
                if second.challenge is not None:
                    second._leave_challenge()
                second.close()
                first.close()

    def test_failed_classic_save_cancel_preserves_active_game(self):
        from huarongdao.gui import MainWindow
        with TemporaryDirectory() as td:
            win = MainWindow()
            try:
                win.enable_progress(Path(td))
                win._make_move(8, 1, 0, 1)
                classic = win.game
                with patch.object(win, '_save_progress', return_value=False), patch.object(win, '_ask_save_failure', return_value='cancel'):
                    self.assertFalse(win._start_challenge(ChallengeSpec('classic', 'time', 'extreme'), Clock()))
                self.assertIs(win.game, classic)
                self.assertIsNone(win.challenge)
                self.assertTrue(classic.running)
                self.assertEqual(classic.steps, 1)
            finally:
                win.close()

    def test_setup_time_excluded_and_terminal_snapshot_drives_labels(self):
        from huarongdao.gui import MainWindow
        with TemporaryDirectory() as td:
            win = MainWindow()
            try:
                win.enable_progress(Path(td))
                clock = Clock()
                original = win._reset_board_display
                def slow_setup():
                    clock.now += 2.5
                    original()
                with patch.object(win, '_reset_board_display', side_effect=slow_setup):
                    self.assertTrue(win._start_challenge(ChallengeSpec('classic', 'time', 'extreme'), clock))
                self.assertEqual(win.challenge.elapsed, 0)
                clock.now += win.challenge.spec.limit
                win._update_stats()
                self.assertEqual(win.challenge.status, 'timeout')
                self.assertEqual(win.challenge.result.milliseconds, win.challenge.spec.limit * 1000)
                self.assertEqual(win.challenge_bar.value(), 0)
                self.assertFalse(win.board.isEnabled())
                self.assertTrue(win.hint_card.isHidden())
                win._leave_challenge()
                self.assertFalse(win.hint_card.isHidden())
            finally:
                if win.challenge is not None:
                    win._leave_challenge()
                win.close()

    def test_readonly_start_can_be_cancelled(self):
        from huarongdao.gui import MainWindow
        with TemporaryDirectory() as td:
            first, second = MainWindow(), MainWindow()
            try:
                first.enable_progress(Path(td))
                second.enable_progress(Path(td))
                original = second.game
                with patch.object(second, '_confirm_discard', return_value=False):
                    self.assertFalse(second._start_challenge(ChallengeSpec('classic', 'time', 'extreme'), Clock()))
                self.assertIs(second.game, original)
                self.assertIsNone(second.challenge)
            finally:
                second.close()
                first.close()

    def test_budget_preview_and_result_dialog(self):
        from huarongdao.gui import MainWindow
        from PySide6.QtWidgets import QLabel
        with TemporaryDirectory() as td:
            win = MainWindow()
            try:
                win.enable_progress(Path(td))
                clock = Clock()
                self.assertTrue(win._start_challenge(ChallengeSpec('classic', 'steps', 'extreme'), clock))
                board = win.board
                board._selected = {8}
                board._targets_visible = True
                board.challenge_budget = 1
                self.assertEqual(len(board._hint_rects()), 1)
                board.challenge_budget = 0
                self.assertEqual(board._hint_rects(), ())
                before = win.game.positions
                board._request_move(1, 0, 1)
                self.assertEqual(win.game.positions, before)
                win._leave_challenge()
                self.assertTrue(win._start_challenge(ChallengeSpec('classic', 'time', 'extreme'), clock))
                clock.now += win.challenge.spec.limit
                win._update_stats()
                self.assertIsNone(win._challenge_dialog)
                win._show_challenge_result()
                result = win._challenge_dialog
                self.assertIsNotNone(result)
                labels = ' '.join(label.text() for label in result.findChildren(QLabel))
                self.assertIn(tr(win.language, 'challenge_timeout'), labels)
                win._show_challenge_result()
                self.assertIs(win._challenge_dialog, result)
                win._leave_challenge()
                self.assertIsNone(win._challenge_dialog)
            finally:
                if win.challenge is not None:
                    win._leave_challenge()
                win.close()
