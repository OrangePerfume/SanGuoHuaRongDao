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


if __name__ == '__main__':
    unittest.main()
