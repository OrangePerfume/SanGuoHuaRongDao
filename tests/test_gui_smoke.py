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

            click(1, 4)
            self.assertEqual(board._selected, {8})
            self.assertTrue(board._targets_visible)
            # 键盘移动：保留选择用于连续操作，但关闭空格高亮
            win._make_move(8, 1, 0, 1)
            self.assertEqual(win.game.positions[8], 18)
            self.assertEqual(board._selected, {8})
            self.assertFalse(board._targets_visible)
            click(2, 4)  # 再次点击选中棋子可重新查看可达空位
            self.assertTrue(board._targets_visible)
            win._undo()
            self.assertEqual(board._selected, set())
            self.assertFalse(board._targets_visible)
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
