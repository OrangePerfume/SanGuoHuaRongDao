"""Regression checks for keyboard selection and normal Qt focus traversal."""
import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'Requires PySide6 / Qt')
class KeyboardNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_tab_can_leave_board_in_both_directions(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from huarongdao.gui import MainWindow
        win = MainWindow()
        try:
            win.show()
            win.activateWindow()
            self.app.processEvents()
            board = win.board
            board.setFocus()
            self.app.processEvents()
            self.assertIs(self.app.focusWidget(), board)
            QTest.keyClick(board, Qt.Key.Key_Tab)
            self.assertIsNotNone(self.app.focusWidget())
            self.assertIsNot(self.app.focusWidget(), board)
            self.assertEqual(board._selected, set())
            board.setFocus()
            QTest.keyClick(board, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
            self.assertIsNotNone(self.app.focusWidget())
            self.assertIsNot(self.app.focusWidget(), board)
            self.assertEqual(board._selected, set())
            self.assertEqual(win.game.steps, 0)
        finally:
            win.close()

    def test_q_e_select_and_wrap_then_arrows_move_selected_piece(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from huarongdao.gui import MainWindow
        win = MainWindow()
        try:
            win.show()
            self.app.processEvents()
            board = win.board
            board.setFocus()
            QTest.keyClick(board, Qt.Key.Key_E)
            self.assertEqual(board._selected, {0})
            QTest.keyClick(board, Qt.Key.Key_Q)
            self.assertEqual(board._selected, {9})
            QTest.keyClick(board, Qt.Key.Key_Q)
            self.assertEqual(board._selected, {8})
            self.assertTrue(board._targets_visible)
            QTest.keyClick(board, Qt.Key.Key_Right)
            self.assertEqual(win.game.positions[8], 17)
            self.assertEqual(win.game.steps, 1)
            win._pause()
            QTest.keyClick(board, Qt.Key.Key_E)
            self.assertEqual(board._selected, {8})
            self.assertEqual(win.game.steps, 1)
        finally:
            win.close()


if __name__ == '__main__':
    unittest.main()
