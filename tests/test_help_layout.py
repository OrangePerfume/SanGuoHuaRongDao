"""Right-hand help area: readable under minimum window size and at larger DPI."""
from pathlib import Path
import importlib.util
import unittest

PROJECT = Path(__file__).resolve().parents[1]


class HelpLayoutSourceTests(unittest.TestCase):
    def test_scrollable_and_wrapped_help_exists(self):
        gui = (PROJECT / 'huarongdao' / 'gui.py').read_text(encoding='utf-8')
        self.assertIn('QScrollArea(side)', gui)
        self.assertIn('self.side_scroll = QScrollArea()', gui)
        self.assertIn('self.side_scroll.setWidgetResizable(True)', gui)
        self.assertIn('self.help_scroll.setWidgetResizable(True)', gui)
        self.assertIn('self.help_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)', gui)
        self.assertIn('description_label.setWordWrap(True)', gui)
        self.assertIn('side_layout.addWidget(self.help_scroll, 1)', gui)
        self.assertIn('foot.setWordWrap(True)', gui)


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'Requires PySide6 to verify real Qt geometry')
class HelpLayoutQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_help_layout_at_minimum_and_default_window_sizes(self):
        from huarongdao.gui import MainWindow
        win = MainWindow()
        try:
            for width, height in ((990, 700), (1170, 840)):
                with self.subTest(size=(width, height)):
                    win.resize(width, height)
                    win.show()
                    self.app.processEvents()
                    outer = win.side_scroll
                    self.assertEqual(outer.horizontalScrollBar().maximum(), 0)
                    if outer.widget().height() > outer.viewport().height():
                        self.assertGreater(outer.verticalScrollBar().maximum(), 0)
                    scroll = win.help_scroll
                    self.assertGreater(scroll.viewport().width(), 100)
                    self.assertGreater(scroll.viewport().height(), 65)
                    self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
                    self.assertEqual(len(win.help_labels), 6)
                    self.assertTrue(all(label.wordWrap() for label in win.help_labels))
                    # If the text doesn't fit vertically, Qt must expose a scroll range.
                    last = win.help_labels[-1]
                    visible_bottom = last.mapTo(scroll.viewport(), last.rect().bottomLeft()).y()
                    if visible_bottom > scroll.viewport().height():
                        self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
                        scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
                        self.app.processEvents()
                        visible_bottom = last.mapTo(scroll.viewport(), last.rect().bottomLeft()).y()
                        self.assertLessEqual(visible_bottom, scroll.viewport().height() + 4)
        finally:
            win.close()

    def test_footer_wraps_and_help_text_survives_resize(self):
        from PySide6.QtWidgets import QLabel
        from huarongdao.gui import MainWindow
        win = MainWindow()
        try:
            win.resize(990,700)
            win.show()
            self.app.processEvents()
            footer = next(label for label in win.findChildren(QLabel)
                          if label.text().startswith('提示：绿色轮廓'))
            self.assertTrue(footer.wordWrap())
            self.assertIn('整组移动可一次撤销', win.help_labels[-1].text())
            win.resize(1170,840)
            self.app.processEvents()
            self.assertTrue(all(label.isVisible() for label in win.help_labels))
        finally:
            win.close()


if __name__ == '__main__':
    unittest.main()
