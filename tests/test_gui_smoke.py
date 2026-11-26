"""GUI 启动和资源绘制烟雾测试；未安装 Qt 时跳过。

在 Windows 运行 build.cmd 时 Qt 已安装，自动纳入构建门禁。
"""
import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec('PySide6'), '当前环境没有安装 PySide6')
class GuiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_construct_render_and_move(self):
        from PySide6.QtGui import QPixmap
        from PySide6.QtCore import QPointF
        from huarongdao.gui import MainWindow
        win = MainWindow()
        try:
            win.resize(1170,840)
            win.show()
            self.app.processEvents()
            self.assertFalse(any(x.isNull() for x in win.board._images))
            self.assertEqual(win.board._at(QPointF(-100, -100)), None)
            canvas = QPixmap(win.size())
            win.render(canvas)
            self.assertFalse(canvas.isNull())
            win._make_move(8, 1, 0, 1)
            self.assertEqual(win.game.steps, 1)
            self.assertEqual(win.game.positions[8], 17)
            win._undo()
            self.assertEqual(win.game.steps, 0)
        finally:
            win.close()

    def test_click_destination_and_ctrl_multiselect(self):
        """模拟真实按下/松开，确保点击空位和 Ctrl 多选连通模型。"""
        from PySide6.QtCore import QPointF, Qt
        from huarongdao.gui import MainWindow

        class MouseEvent:
            def __init__(self, position, modifiers=Qt.KeyboardModifier.NoModifier):
                self._position = position
                self._modifiers = modifiers

            def button(self):
                return Qt.MouseButton.LeftButton

            def position(self):
                return self._position

            def modifiers(self):
                return self._modifiers

        win = MainWindow()
        try:
            win.resize(1170, 840)
            win.show()
            self.app.processEvents()
            board = win.board
            x0, y0, cell = board._layout()

            def click(x, y, mods=Qt.KeyboardModifier.NoModifier):
                point = QPointF(x0 + (x + 0.5) * cell, y0 + (y + 0.5) * cell)
                event = MouseEvent(point, mods)
                board.mousePressEvent(event)
                board.mouseReleaseEvent(event)

            click(0, 4)  # 单击选中左下角小兵
            self.assertEqual(board._selected, {8})
            self.assertTrue(board._targets_visible)
            click(2, 4)  # 再点击空位，自动右移两格
            self.assertEqual(win.game.positions[8], 18)
            self.assertEqual(win.game.steps, 2)
            self.assertEqual(board._selected, set())  # 成功移动后不残留选中状态
            self.assertFalse(board._targets_visible)
            board.clear_animation()  # 以下操作针对动画结束后的棋局
            click(2, 4)  # 重新选择刚移动的小兵
            click(3, 4, Qt.KeyboardModifier.ControlModifier)  # 加选另一名小兵
            self.assertEqual(board._selected, {8, 9})
            self.assertTrue(board._targets_visible)
            click(1, 4)  # 两枚士兵整体向左 1 格
            self.assertEqual(win.game.positions[8:10], (17, 18))
            self.assertEqual(win.game.steps, 4)
            self.assertEqual(board._selected, set())
            self.assertFalse(board._targets_visible)
            win._undo()
            self.assertEqual(win.game.positions[8:10], (18, 19))
            self.assertEqual(win.game.steps, 2)
            self.assertEqual(board._selected, set())
        finally:
            win.close()



    def test_hint_lifecycle_invalid_mouse_and_keyboard(self):
        """非法点击提示仍在；成功拖动/键盘移动不遗留空格提示。"""
        from PySide6.QtCore import QPointF, Qt
        from huarongdao.gui import MainWindow

        class MouseEvent:
            def __init__(self, pos, button=Qt.MouseButton.LeftButton):
                self._pos = pos
                self._button = button

            def button(self):
                return self._button

            def position(self):
                return self._pos

            def modifiers(self):
                return Qt.KeyboardModifier.NoModifier

        win = MainWindow()
        try:
            win.resize(1170, 840)
            win.show()
            self.app.processEvents()
            board = win.board
            x0, y0, unit = board._layout()

            def point(x, y):
                return QPointF(x0 + (x + 0.5) * unit, y0 + (y + 0.5) * unit)

            def click(x, y):
                ev = MouseEvent(point(x, y))
                board.mousePressEvent(ev)
                board.mouseReleaseEvent(ev)

            click(0, 4)
            self.assertEqual(board._selected, {8})
            self.assertTrue(board._targets_visible)
            click(3, 0)  # 点击被赵云占据的格子：切换选中目标，而非移动
            self.assertEqual(board._selected, {3})
            self.assertTrue(board._targets_visible)
            click(1, 4)  # 赵云不可移动到该空位，原选择不变
            self.assertEqual(board._selected, {3})
            self.assertTrue(board._targets_visible)
            self.assertEqual(win.game.steps, 0)

            click(0, 4)
            # 模拟从左下角拖动到右侧空位
            start = MouseEvent(point(0, 4))
            end = MouseEvent(point(1, 4))
            board.mousePressEvent(start)
            board.mouseMoveEvent(end)
            board.mouseReleaseEvent(end)
            self.assertEqual(win.game.positions[8], 17)
            self.assertEqual(board._selected, set())
            self.assertFalse(board._targets_visible)

            board.clear_animation()
            click(1, 4)
            self.assertEqual(board._selected, {8})
            self.assertTrue(board._targets_visible)
            # 键盘移动：保留选择用于连续操作，但关闭空格高亮
            win._make_move(8, 1, 0, 1)
            self.assertEqual(win.game.positions[8], 18)
            self.assertEqual(board._selected, {8})
            self.assertFalse(board._targets_visible)
            board.clear_animation()
            click(2, 4)  # 再次点击选中棋子可重新查看可达空位
            self.assertTrue(board._targets_visible)
            win._undo()
            self.assertEqual(board._selected, set())
            self.assertFalse(board._targets_visible)
        finally:
            win.close()

    def test_animation_hit_testing_uses_visible_position(self):
        """Fix #4: clicks must follow the visible piece, not its logical destination."""
        from PySide6.QtCore import QPointF, Qt
        from huarongdao.gui import MainWindow

        class MouseEvent:
            def __init__(self, pos, modifiers):
                self._pos = pos
                self._modifiers = modifiers

            def button(self):
                return Qt.MouseButton.LeftButton

            def position(self):
                return self._pos

            def modifiers(self):
                return self._modifiers

        win = MainWindow()
        try:
            win.resize(1170, 840)
            win.show()
            self.app.processEvents()
            board = win.board

            def point(x, y=4.5):
                left, top, unit = board._layout()
                return QPointF(left + x * unit, top + y * unit)

            def click(x, modifiers=Qt.KeyboardModifier.NoModifier):
                event = MouseEvent(point(x), modifiers)
                board.mousePressEvent(event)
                board.mouseReleaseEvent(event)

            win._make_move(8, 1, 0, 1)
            self.assertEqual(win.game.positions[8], 17)
            # Freeze a reproducible intermediate frame without waiting for Qt.
            board._animation.stop()
            board._motion.set_progress(.25)
            self.assertEqual(board._at(point(.5)), 8)
            self.assertIsNone(board._at(point(1.5)))
            click(1.5)
            self.assertEqual(board._selected, set())
            click(.5)
            self.assertEqual(board._selected, {8})
            self.assertTrue(board._targets_visible)
            click(3.5, Qt.KeyboardModifier.ControlModifier)
            self.assertEqual(board._selected, {8, 9})
            self.assertEqual(win.game.steps, 1)

            board._motion.set_progress(.75)
            self.assertIsNone(board._at(point(.5)))
            self.assertEqual(board._at(point(1.5)), 8)
            board.resize(560, 640)
            self.assertEqual(board._at(point(1.5)), 8)
            self.assertIsNone(board._at(point(.5)))

            # Retarget a still-moving soldier together with another piece.
            win._make_group_move((8, 9), -1, 0, 1)
            self.assertEqual(win.game.positions[8:10], (16, 18))
            board._animation.stop()
            board._motion.set_progress(.25)
            self.assertEqual(board._at(point(1.0625)), 8)
            self.assertEqual(board._at(point(3.25)), 9)
            win._undo()
            board._animation.stop()
            board._motion.set_progress(.4)
            self.assertEqual(win.game.positions[8:10], (17, 19))
            self.assertEqual(board._at(board._displayed_piece_rect(8).center()), 8)
            self.assertEqual(board._at(board._displayed_piece_rect(9).center()), 9)
            board.clear_animation()
            self.assertEqual(board._at(point(1.5)), 8)
            self.assertEqual(board._at(point(3.5)), 9)
            self.assertIsNone(board._at(point(.5)))
            self.assertIsNone(board._at(point(-.5)))
            self.assertEqual(win.game.steps, 1)
        finally:
            win.close()

    def test_hit_margin_and_animation_overlap_priority(self):
        from PySide6.QtCore import QPointF
        from huarongdao.gui import MainWindow

        win = MainWindow()
        try:
            board = win.board
            board.resize(660, 735)
            left, top, unit = board._layout()

            def point(x, y=4.5):
                return QPointF(left + x * unit, top + y * unit)

            # The original occupied cell remains clickable right up to its edge.
            self.assertEqual(board._at(point(.01)), 8)
            self.assertEqual(board._at(point(.99)), 8)
            self.assertIsNone(board._at(point(1.0)))
            self.assertIsNone(board._at(point(-.01)))
            # Synthetic overlapping visual rectangles (no model mutation).
            board._motion.starts = {8: (2.0, 4.0), 9: (2.25, 4.0)}
            board._motion.targets = dict(board._motion.starts)
            board._motion.set_progress(.5)
            self.assertEqual(board._at(point(2.5)), 9)
            # A lower piece's body must beat the higher piece's margin.
            self.assertEqual(board._at(point(2.26)), 8)
            board.clear_animation()
            self.assertEqual(board._at(point(.5)), 8)
            self.assertIsNone(board._at(point(1.5)))
            self.assertEqual(win.game.steps, 0)
        finally:
            win.close()

    def test_empty_target_rechecked_during_real_qt_animation(self):
        from PySide6.QtCore import QPointF, Qt
        from PySide6.QtTest import QTest
        from huarongdao.gui import MainWindow

        win = MainWindow()
        try:
            win.show()
            self.app.processEvents()
            board = win.board
            for speed in ('slow', 'normal', 'fast'):
                with self.subTest(speed=speed):
                    win.game.reset()
                    board.clear_animation()
                    board.clear_selection()
                    board.set_animation_speed(speed)
                    left, top, unit = board._layout()

                    def point(x):
                        return QPointF(left + x * unit, top + 4.5 * unit)

                    def click(x):
                        QTest.mouseClick(board, Qt.MouseButton.LeftButton,
                                         Qt.KeyboardModifier.NoModifier, point(x).toPoint())

                    win._make_move(8, 1, 0, 2)
                    self.assertEqual(win.game.positions[8], 18)
                    # Advance a real QVariantAnimation deterministically. Pause
                    # its clock so CI timing cannot race the mouse events.
                    animation = board._animation
                    animation.pause()
                    duration = animation.duration()
                    animation.setCurrentTime(max(1, duration // 20))
                    self.assertEqual(board._at(point(.5)), 8)
                    click(.5)
                    self.assertEqual(board._selected, {8})
                    # Visually empty, but reserved by the logical destination.
                    self.assertIsNone(board._at(point(2.5)))
                    QTest.mousePress(board, Qt.MouseButton.LeftButton,
                                     Qt.KeyboardModifier.NoModifier, point(2.5).toPoint())
                    self.assertIsNone(board._pressed_pos)
                    QTest.mouseRelease(board, Qt.MouseButton.LeftButton,
                                       Qt.KeyboardModifier.NoModifier, point(2.5).toPoint())
                    # A valid empty cell at press becomes visually occupied
                    # during the gesture. It must not trigger a move on release.
                    self.assertEqual(board._empty_target_cell(point(1.5)), (1, 4))
                    QTest.mousePress(board, Qt.MouseButton.LeftButton,
                                     Qt.KeyboardModifier.NoModifier, point(1.5).toPoint())
                    self.assertIsNotNone(board._pressed_pos)
                    animation.setCurrentTime(duration // 5)
                    self.assertEqual(board._at(point(1.5)), 8)
                    QTest.mouseRelease(board, Qt.MouseButton.LeftButton,
                                       Qt.KeyboardModifier.NoModifier, point(1.5).toPoint())
                    self.assertEqual(win.game.positions[8], 18)
                    self.assertEqual(win.game.steps, 2)
                    self.assertEqual(board._selected, {8})
                    self.assertIsNone(board._pressed_pos)
                    # A genuinely empty target remains usable after animation.
                    board.clear_animation()
                    click(1.5)
                    self.assertEqual(win.game.positions[8], 17)
                    self.assertEqual(win.game.steps, 3)
        finally:
            win.close()

    def test_drag_from_visible_piece_keeps_legal_preview_and_undo(self):
        from PySide6.QtCore import QPointF, Qt
        from huarongdao.gui import MainWindow

        class MouseEvent:
            def __init__(self, point):
                self._point = point

            def button(self):
                return Qt.MouseButton.LeftButton

            def position(self):
                return self._point

            def modifiers(self):
                return Qt.KeyboardModifier.NoModifier

        win = MainWindow()
        try:
            board = win.board
            board.resize(660, 735)
            left, top, unit = board._layout()
            win._make_move(8, 1, 0, 1)
            board._animation.stop()
            board._motion.set_progress(.25)
            origin = board._motion.displayed(8, win.game.positions)
            press = MouseEvent(QPointF(left + .5 * unit, top + 4.5 * unit))
            release = MouseEvent(QPointF(left + 1.5 * unit, top + 4.5 * unit))
            board.mousePressEvent(press)
            self.assertEqual(board._selected, {8})
            board.mouseMoveEvent(release)
            self.assertEqual(board._preview, {8: 18})
            self.assertEqual(win.game.positions[8], 17)
            board.mouseReleaseEvent(release)
            self.assertEqual(win.game.positions[8], 18)
            self.assertEqual(win.game.steps, 2)
            self.assertEqual(board._motion.displayed(8, win.game.positions), origin)
            self.assertIsNone(board._preview)
            win._undo()
            self.assertEqual(win.game.positions[8], 17)
            self.assertEqual(win.game.steps, 1)
        finally:
            win.close()

    def test_hint_rect_matches_entire_piece_footprint(self):
        """真实 Qt 矩形尺寸：曹操/横将/竖将分别是 2×2 / 2×1 / 1×2。"""
        from huarongdao.gui import MainWindow
        from PySide6.QtGui import QPixmap

        win = MainWindow()
        try:
            win.resize(1170, 840)
            win.show()
            self.app.processEvents()
            board = win.board
            for state, selection, width, height in (
                ((1, 9, 0, 11, 12, 14, 8, 19, 17, 13), 0, 2, 2),
                ((1, 9, 0, 3, 12, 11, 13, 14, 17, 19), 1, 2, 1),
                ((1, 9, 0, 3, 8, 11, 13, 14, 17, 19), 4, 1, 2),
                ((1, 16, 9, 11, 8, 10, 0, 4, 18, 19), 3, 1, 3),
                ((1, 16, 9, 3, 8, 11, 0, 4, 10, 14), 1, 3, 1),
                (win.game.positions, 8, 1, 1),
            ):
                win.game.replace_for_test(state)
                board._selected = {selection}
                board._emit_selection()
                _, _, unit = board._layout()
                hints = board._hint_rects()
                self.assertGreater(len(hints), 0)
                if width == 3 or height == 3:
                    self.assertEqual(len(hints), 1)
                for hint in hints:
                    self.assertAlmostEqual(hint.width(), width * unit - 14)
                    self.assertAlmostEqual(hint.height(), height * unit - 14)
                canvas = QPixmap(board.size())
                board.render(canvas)
                self.assertFalse(canvas.isNull())
                board.hide_targets()
                self.assertEqual(board._hint_rects(), ())
        finally:
            win.close()



if __name__ == '__main__':
    unittest.main()
