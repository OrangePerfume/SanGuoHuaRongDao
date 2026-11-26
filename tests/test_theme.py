"""Red Cliffs resources, board/plaque geometry, and redesigned UI behavior."""
from pathlib import Path
import importlib.util
import unittest
from unittest.mock import patch
from PIL import Image
from huarongdao.theme import board_layout, plaque_geometry, normalize_dimming
from huarongdao.i18n import LANGUAGES, tr, selected_names

ROOT = Path(__file__).resolve().parents[1]


class ThemeTests(unittest.TestCase):
    def test_scene_resource_is_valid_and_independent(self):
        with Image.open(ROOT / 'huarongdao/assets/red_cliffs.jpg') as image:
            self.assertGreaterEqual(image.width, 1200)
            self.assertGreaterEqual(image.height, 800)
            self.assertEqual(image.format, 'JPEG')
            image.verify()

    def test_board_plaque_never_overlaps_or_leaves_play_area(self):
        for locale, _ in LANGUAGES:
            for width, height in ((500, 520), (527, 600), (660, 735), (1000, 900)):
                with self.subTest(locale=locale, size=(width, height)):
                    x, y, cell = board_layout(width, height, locale)
                    px, py, pw, ph = plaque_geometry(width, height, locale)
                    self.assertGreaterEqual(cell, 78)
                    self.assertGreaterEqual(x-24, 0)
                    self.assertGreaterEqual(y-66, 0)
                    self.assertLessEqual(y+5*cell+39, height)
                    self.assertGreater(px, x+4*cell+24)
                    self.assertLessEqual(px+pw, width)
                    self.assertGreaterEqual(py, 0)
                    self.assertLessEqual(py+ph, height)

    def test_dimming_bounds_and_invalid_preferences(self):
        for value, expected in [(None,22), ('oops',22), ('45',45), (-20,0), (99,65), (float('inf'),22)]:
            self.assertEqual(normalize_dimming(value), expected)

    def test_new_controls_have_all_translations(self):
        for locale, _ in LANGUAGES:
            for key in ('settings','about','language_heading','background_dim','selection_heading','solution_heading','solution_idle'):
                self.assertTrue(tr(locale, key))


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'Requires PySide6 / Qt')
class ThemeGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_default_collapsed_help_expands_without_changing_game(self):
        from huarongdao.gui import MainWindow
        win = MainWindow()
        try:
            win.show()
            self.app.processEvents()
            before = (win.game.positions, win.game.steps, win.game.running)
            self.assertFalse(win.help_toggle.isChecked())
            self.assertTrue(win.help_scroll.isHidden())
            win.help_toggle.click()
            self.app.processEvents()
            self.assertTrue(win.help_scroll.isVisible())
            self.assertGreater(win.help_scroll.viewport().height(),65)
            win.help_toggle.click()
            self.assertTrue(win.help_scroll.isHidden())
            self.assertEqual(before,(win.game.positions, win.game.steps, win.game.running))
        finally:
            win.close()

    def test_three_languages_selection_plaque_and_top_bar(self):
        from PySide6.QtGui import QFontMetrics
        from huarongdao.gui import MainWindow
        win = MainWindow()
        try:
            win.show()
            for locale,_ in LANGUAGES:
                win.set_language(locale,persist=False)
                for width,height in ((990,700),(1170,840)):
                    win.resize(width,height)
                    for selection in ((), (8,), (0,1), tuple(range(10))):
                        win.board._selected = set(selection)
                        win.board._emit_selection()
                        self.app.processEvents()
                        plaque = win.selected_info
                        self.assertEqual(plaque.toolTip(), tr(locale,'selection_prefix',names=selected_names(locale,selection)))
                        self.assertTrue(win.board.rect().contains(plaque.geometry()))
                        self.assertFalse(win.board._piece_rect(0).toAlignedRect().intersects(plaque.geometry()))
                        target, flags, text, f = plaque.text_layout()
                        bounds = QFontMetrics(f).boundingRect(target, flags, text)
                        self.assertLessEqual(bounds.height(),target.height()+2)
                        self.assertLessEqual(bounds.width(),target.width()+2)
                    for label in (win.title_label,win.subtitle_label):
                        self.assertFalse(label.wordWrap())
                        self.assertLessEqual(label.fontMetrics().horizontalAdvance(label.text()),label.contentsRect().width()+2)
                    self.assertEqual(win.side_scroll.horizontalScrollBar().maximum(),0)
                    self.assertTrue(win.settings_button.isVisible())
                    self.assertTrue(win.about_button.isVisible())
                    self.assertFalse(win.grab().isNull())
        finally:
            win.close()

    def test_settings_cancel_and_apply_persist_without_reset(self):
        from PySide6.QtWidgets import QDialog, QSlider, QComboBox
        from huarongdao.gui import MainWindow
        win=MainWindow()
        keys=('ui/background_dim','ui/language','game/animation_speed')
        before_settings={key:win.settings.value(key) for key in keys}
        try:
            win._make_move(8,1,0,1)
            before=(win.game.positions,win.game.steps,tuple(win.game.history))
            previous_dim=win.background_dim
            def edit(dialog, accepted):
                dialog.findChild(QSlider).setValue(37)
                for combo in dialog.findChildren(QComboBox):
                    if combo.findData('en')>=0: combo.setCurrentIndex(combo.findData('en'))
                    if combo.findData('fast')>=0: combo.setCurrentIndex(combo.findData('fast'))
                return QDialog.DialogCode.Accepted if accepted else QDialog.DialogCode.Rejected
            with patch.object(win,'_exec_preferences_dialog',side_effect=lambda dialog:edit(dialog,False)):
                win._open_settings()
            self.assertEqual(win.background_dim,previous_dim)
            with patch.object(win,'_exec_preferences_dialog',side_effect=lambda dialog:edit(dialog,True)):
                win._open_settings()
            self.assertEqual(win.background_dim,37)
            self.assertEqual(win.background.dim,37)
            self.assertEqual(win.language,'en')
            self.assertEqual(win.animation_speed,'fast')
            self.assertEqual(int(win.settings.value('ui/background_dim')),37)
            self.assertEqual(before,(win.game.positions,win.game.steps,tuple(win.game.history)))
        finally:
            for key,value in before_settings.items():
                if value is None: win.settings.remove(key)
                else: win.settings.setValue(key,value)
            win.settings.sync()
            win.close()
