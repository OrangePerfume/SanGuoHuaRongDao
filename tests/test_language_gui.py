"""Runtime language switching: no game restart, no lost game state, no stale text."""
import importlib.util
import unittest


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'Requires PySide6 / Qt')
class LanguageGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_menu_has_three_exclusive_languages_and_switches_immediately(self):
        from huarongdao.gui import MainWindow
        win = MainWindow()
        before = win.settings.value('ui/language')
        try:
            win.set_language('zh-CN', persist=False)
            self.assertEqual(set(win.language_actions), {'zh-CN', 'zh-TW', 'en'})
            self.assertEqual(len(win.language_menu.actions()), 3)
            win.language_actions['en'].trigger()
            self.assertEqual(win.language, 'en')
            self.assertIn('Language', win.language_button.text())
            self.assertIn('Three Kingdoms', win.windowTitle())
            self.assertEqual(win.reset_button.text(), 'Restart')
            self.assertEqual(win.pause_button.text(), 'Pause game')
            self.assertTrue(win.language_actions['en'].isChecked())
            self.assertEqual(win.settings.value('ui/language'), 'en')
            win.language_actions['zh-TW'].trigger()
            self.assertEqual(win.language, 'zh-TW')
            self.assertIn('華容道', win.windowTitle())
            self.assertIn('復原', win.undo_button.text())
            self.assertEqual(win.speed_combo.itemText(win.speed_combo.findData('normal')), '標準')
            self.assertTrue(win.language_actions['zh-TW'].isChecked())
        finally:
            if before is None:
                win.settings.remove('ui/language')
            else:
                win.settings.setValue('ui/language', before)
            win.settings.sync()
            win.close()

    def test_active_puzzle_and_hidden_hints_survive_language_change(self):
        from huarongdao.gui import MainWindow
        win = MainWindow()
        try:
            win.set_language('zh-CN', persist=False)
            win._make_move(8, 1, 0, 1)
            win.board._selected = {8}
            win.board._targets_visible = False  # keyboard movement hides target highlights
            before = (win.game.positions, win.game.steps, win.game.running,
                      win.game.paused, len(win.game.history))
            win.set_language('en', persist=False)
            after = (win.game.positions, win.game.steps, win.game.running,
                     win.game.paused, len(win.game.history))
            self.assertEqual(before, after)
            self.assertEqual(win.board._selected, {8})
            self.assertFalse(win.board._targets_visible)
            self.assertIn('Soldier', win.selected_info.text())
            self.assertIn('Group movement', win.help_sections)
            self.assertEqual(len(win.help_labels), len(win.help_sections))
            self.assertEqual(win.board.language, 'en')
            self.assertEqual(win.steps_label.text(), '1')
            win._undo()
            self.assertEqual(win.game.steps, 0)
        finally:
            win.close()

    def test_persisted_language_is_loaded_on_next_window(self):
        from huarongdao.gui import MainWindow
        from PySide6.QtCore import QSettings
        settings = QSettings('OrangePerfume', 'SanGuoHuaRongDao')
        before = settings.value('ui/language')
        first = None
        second = None
        try:
            first = MainWindow()
            first.set_language('en')
            second = MainWindow()
            self.assertEqual(second.language, 'en')
            self.assertEqual(second.board.language, 'en')
            self.assertEqual(second.speed_combo.itemText(1), 'Normal')
            second.resize(990, 700)
            second.show()
            self.app.processEvents()
            self._assert_sidebar_fits(second)
        finally:
            if second is not None:
                second.close()
            if first is not None:
                first.close()
            if before is None:
                settings.remove('ui/language')
            else:
                settings.setValue('ui/language', before)
            settings.sync()

    def test_help_panel_and_board_render_in_all_languages(self):
        from PySide6.QtGui import QPixmap
        from huarongdao.gui import MainWindow
        from huarongdao.i18n import HELP_IDS
        win = MainWindow()
        try:
            # Exercise both switching directions, minimum/default sizes and
            # repeated resize with the same window (including stale size hints).
            for locale in ('zh-CN', 'zh-TW', 'en', 'zh-CN', 'en'):
                win.set_language(locale, persist=False)
                for size in ((990, 700), (1170, 840), (990, 700)):
                    with self.subTest(locale=locale, size=size):
                        win.resize(*size)
                        win.show()
                        self.app.processEvents()
                        image = QPixmap(win.size())
                        win.render(image)
                        self.assertFalse(image.isNull())
                        self._assert_sidebar_fits(win)
                        self.assertEqual(len(win.help_labels), len(HELP_IDS))
                        self.assertTrue(all(x.wordWrap() for x in win.help_labels))
                        self.assertTrue(all(x.text().strip() for x in win.help_labels))
                        self.assertTrue(win.footer_label.wordWrap())
                        self.assertTrue(win.language_button.isVisible())
        finally:
            win.close()

    def _assert_sidebar_fits(self, win):
        # A hidden scrollbar is not evidence of fitting: inspect both range
        # and the actual content geometry, including the nested help viewport.
        for scroll in (win.side_scroll, win.help_scroll):
            self.assertGreater(scroll.viewport().width(), 100)
            self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
            self.assertLessEqual(scroll.widget().width(), scroll.viewport().width())
            content = scroll.widget()
            for i in range(content.layout().count()):
                item = content.layout().itemAt(i)
                if item.widget() is None and item.layout() is None:
                    continue
                rect = item.geometry()
                self.assertGreaterEqual(rect.left(), 0)
                self.assertLess(rect.right(), content.width())
        for label in (win.chapter_header, win.intro_label, win.best_label,
                      win.selected_info, win.help_heading_label,
                      *win.help_titles, *win.help_labels):
            self.assertTrue(label.wordWrap())
            self.assertGreater(label.width(), 0)
            # A horizontally fitting label must also have enough height for
            # the translated wrapped text, not just hide overflowing lines.
            needed = label.heightForWidth(label.width())
            if needed >= 0:
                self.assertGreaterEqual(label.height() + 2, needed, label.text())
        for button in (win.reset_button, win.undo_button, win.pause_button):
            self.assertGreaterEqual(button.width(), button.minimumSizeHint().width())

    def test_long_english_selection_and_record_fit_sidebar(self):
        from huarongdao.gui import MainWindow
        from huarongdao.i18n import selected_names
        win = MainWindow()
        try:
            win.set_language('en', persist=False)
            win.resize(990, 700)
            win.show()
            win.best = {'steps': 123456, 'seconds': 98765}
            win._update_stats()
            win._on_selection_changed(selected_names('en', tuple(range(10))))
            self.app.processEvents()
            self._assert_sidebar_fits(win)
            self.assertIn('Huang Zhong', win.selected_info.text())
            self.assertIn('123456', win.best_label.text())
        finally:
            win.close()

    def test_pause_and_speed_controls_keep_state_during_translation(self):
        from huarongdao.gui import MainWindow
        win = MainWindow()
        try:
            win.set_language('zh-CN', persist=False)
            win._make_move(8, 1, 0, 1)
            win._pause()
            self.assertTrue(win.game.paused)
            duration = win.board.animation_duration_ms
            win.set_language('en', persist=False)
            self.assertTrue(win.game.paused)
            self.assertEqual(win.pause_button.text(), 'Resume game')
            self.assertEqual(win.board.animation_duration_ms, duration)
            win.set_language('zh-TW', persist=False)
            self.assertEqual(win.pause_button.text(), '繼續遊戲')
            self.assertEqual(win.board.animation_duration_ms, duration)
        finally:
            win.close()


if __name__ == '__main__':
    unittest.main()
