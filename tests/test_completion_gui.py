"""Regression tests for exactly-once completion notifications."""
import importlib.util
import unittest
from unittest.mock import Mock, patch


# Cao Cao is one legal downward move from the exit; the remaining pieces
# occupy every cell except the two destination cells at the bottom.
NEAR_WIN = (9, 1, 0, 3, 8, 11, 5, 6, 16, 19)


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'Requires PySide6 / Qt')
class CompletionGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from huarongdao.core import valid
        from huarongdao.gui import MainWindow
        self.assertTrue(valid(NEAR_WIN))
        self.win = MainWindow()
        self.addCleanup(self.win.close)
        self.win.game.replace_for_test(NEAR_WIN)
        self.win._show_win_dialog = Mock()
        self.win.board.set_animation_speed('slow')

    def complete_animation(self):
        animation = self.win.board._animation
        animation.setCurrentTime(animation.duration())
        self.assertFalse(self.win.board._motion.starts)

    def deliver(self):
        self.assertTrue(self.win._win_timer.isActive())
        self.win._win_timer.stop()
        self.win._win_timer.timeout.emit()

    def test_undo_before_completion_and_rewin_only_notifies_once(self):
        win = self.win
        win._make_move(0, 0, 1, 1)
        self.assertTrue(win.game.finished)
        self.assertTrue(win._win_pending)
        self.assertFalse(win._win_timer.isActive())
        win._undo()
        self.assertFalse(win.game.finished)
        self.assertFalse(win._win_pending)
        win._make_move(0, 0, 1, 1)
        self.assertTrue(win.game.finished)
        win._win()  # A stale callback cannot interrupt the new animation.
        win._show_win_dialog.assert_not_called()
        # Immediate undo/re-win can retarget to the already displayed origin.
        if win.board._motion.starts:
            self.complete_animation()
        self.deliver()
        win._win()
        win._show_win_dialog.assert_called_once_with()
        self.assertFalse(win._win_pending)

    def test_undo_during_post_animation_delay_cancels_notification(self):
        win = self.win
        win._make_move(0, 0, 1, 1)
        self.complete_animation()
        self.assertTrue(win._win_timer.isActive())
        win._undo()
        self.assertFalse(win._win_timer.isActive())
        win._win()
        win._show_win_dialog.assert_not_called()

    def test_group_win_and_speed_change_wait_for_actual_animation(self):
        win = self.win
        win._make_group_move((0, 6), 0, 1, 1)
        self.assertTrue(win.game.finished)
        self.assertEqual(win.game.steps, 2)
        win.board._animation.setCurrentTime(30)
        win.board.set_animation_speed('fast')
        self.assertFalse(win._win_timer.isActive())
        self.complete_animation()
        self.deliver()
        win._show_win_dialog.assert_called_once_with()

    def test_restart_confirmation_cancels_or_resumes_pending_win(self):
        from PySide6.QtWidgets import QMessageBox
        win = self.win
        for answer in (QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes):
            with self.subTest(answer=answer):
                win.game.replace_for_test(NEAR_WIN)
                win.board.clear_animation()
                win._show_win_dialog.reset_mock()
                win._make_move(0, 0, 1, 1)
                with patch('huarongdao.gui.QMessageBox') as message_box:
                    message_box.StandardButton = QMessageBox.StandardButton
                    message_box.Icon = QMessageBox.Icon
                    def confirm():
                        self.complete_animation()
                        win._win()
                        win._show_win_dialog.assert_not_called()
                        return answer
                    message_box.return_value.exec.side_effect = confirm
                    win._restart()
                if answer == QMessageBox.StandardButton.No:
                    self.assertTrue(win.game.finished)
                    self.deliver()
                    win._show_win_dialog.assert_called_once_with()
                else:
                    self.assertFalse(win.game.finished)
                    self.assertFalse(win._win_timer.isActive())
                    self.assertFalse(win._win_pending)
                    win._show_win_dialog.assert_not_called()

    def test_real_timer_notifies_once_and_close_cancels(self):
        from PySide6.QtTest import QTest
        win = self.win
        win._make_move(0, 0, 1, 1)
        self.complete_animation()
        for _ in range(20):
            if win._show_win_dialog.called:
                break
            QTest.qWait(25)
        win._show_win_dialog.assert_called_once_with()
        QTest.qWait(100)
        win._show_win_dialog.assert_called_once_with()
        win._undo()
        win._make_move(0, 0, 1, 1)
        if win.board._motion.starts:
            self.complete_animation()
        win.close()
        self.assertFalse(win._win_timer.isActive())
        self.assertFalse(win._win_pending)
        QTest.qWait(100)
        win._show_win_dialog.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
