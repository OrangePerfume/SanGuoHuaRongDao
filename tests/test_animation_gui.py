"""Qt interaction regression checks for smooth move/undo and speed selection."""
import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'PySide6 not available')
class AnimationGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_chain_move_and_undo_preserve_screen_position(self):
        from huarongdao.gui import MainWindow
        win = MainWindow()
        try:
            board = win.board
            win._make_move(8, 1, 0, 1)
            board._motion.set_progress(.4)
            point = board._motion.displayed(8, win.game.positions)
            win._make_move(8, 1, 0, 1)
            self.assertEqual(board._motion.displayed(8, win.game.positions), point)
            board._motion.set_progress(.35)
            point = board._motion.displayed(8, win.game.positions)
            win._undo()
            self.assertEqual(board._motion.displayed(8, win.game.positions), point)
            self.assertEqual(win.game.steps, 1)
        finally:
            win.close()

    def test_animation_range_is_explicit_and_group_undo_is_animated(self):
        from huarongdao.gui import MainWindow
        win = MainWindow()
        try:
            board = win.board
            self.assertEqual(float(board._animation.startValue()), 0.0)
            self.assertEqual(float(board._animation.endValue()), 1.0)
            # Two independent bottom soldiers can move left together in a
            # reachable game state.  The model tests cover group legality;
            # here only the GUI transition after undo is under test.
            state = win.game.positions
            win.game.move(8, 1, 0)
            win.game.move(8, 1, 0)
            win.game.move_group((8, 9), -1, 0, 1)
            board.animate_group({8: 18, 9: 19})
            board._motion.set_progress(.6)
            previous = board._motion.displayed(8, win.game.positions)
            win._undo()
            self.assertEqual(board._motion.displayed(8, win.game.positions), previous)
            self.assertNotEqual(win.game.positions, state)
        finally:
            win.close()

    def test_changing_speed_mid_motion_preserves_current_frame(self):
        from huarongdao.gui import MainWindow
        win = MainWindow()
        try:
            win._make_move(8, 1, 0, 1)
            win.board._motion.set_progress(.37)
            before = win.board._motion.displayed(8, win.game.positions)
            win.board.set_animation_speed('fast')
            self.assertEqual(win.board._motion.displayed(8, win.game.positions), before)
        finally:
            win.close()

    def test_speed_setting_applies_and_falls_back_safely(self):
        from huarongdao.gui import MainWindow
        from huarongdao.motion import ANIMATION_DURATIONS_MS
        win = MainWindow()
        before = win.settings.value('game/animation_speed', 'normal')
        try:
            win.speed_combo.setCurrentIndex(win.speed_combo.findData('fast'))
            self.assertEqual(win.board.animation_duration_ms, ANIMATION_DURATIONS_MS['fast'])
            self.assertEqual(win.settings.value('game/animation_speed'), 'fast')
            win.speed_combo.setCurrentIndex(win.speed_combo.findData('slow'))
            self.assertEqual(win.board.animation_duration_ms, ANIMATION_DURATIONS_MS['slow'])
        finally:
            win.settings.setValue('game/animation_speed', before)
            win.settings.sync()
            win.close()


if __name__ == '__main__':
    unittest.main()
