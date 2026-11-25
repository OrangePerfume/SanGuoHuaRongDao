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
            for locale in ('zh-CN', 'zh-TW', 'en'):
                with self.subTest(locale=locale):
                    win.set_language(locale, persist=False)
                    win.resize(990, 700)
                    win.show()
                    self.app.processEvents()
                    image = QPixmap(win.size())
                    win.render(image)
                    self.assertFalse(image.isNull())
                    self.assertEqual(win.side_scroll.horizontalScrollBar().maximum(), 0)
                    self.assertEqual(len(win.help_labels), len(HELP_IDS))
                    self.assertTrue(all(x.wordWrap() for x in win.help_labels))
                    self.assertTrue(all(x.text().strip() for x in win.help_labels))
                    self.assertTrue(win.footer_label.wordWrap())
                    self.assertTrue(win.language_button.isVisible())
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
