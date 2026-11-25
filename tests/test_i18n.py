"""Complete runtime localization catalogs must never drift between releases."""
import string
import unittest

from huarongdao.i18n import (
    DEFAULT_LANGUAGE, HELP_IDS, LANGUAGES, PIECE_IDS, STRINGS,
    normalize_language, piece_name, selected_names, tr,
)


class I18nTests(unittest.TestCase):
    def test_three_explicit_locales_and_default(self):
        self.assertEqual(tuple(locale for locale, _ in LANGUAGES), ('zh-CN', 'zh-TW', 'en'))
        self.assertEqual(DEFAULT_LANGUAGE, 'zh-CN')
        self.assertEqual(normalize_language('invalid'), DEFAULT_LANGUAGE)
        self.assertEqual(normalize_language(None), DEFAULT_LANGUAGE)
        self.assertEqual(normalize_language('en'), 'en')

    def test_keys_and_named_format_arguments_match_across_all_locales(self):
        default = STRINGS[DEFAULT_LANGUAGE]
        self.assertGreater(len(default), 50)
        fmt = string.Formatter()
        placeholders = lambda text: {name for _, name, _, _ in fmt.parse(text) if name is not None}
        for locale, _ in LANGUAGES:
            with self.subTest(locale=locale):
                self.assertEqual(default.keys(), STRINGS[locale].keys())
                for key, baseline in default.items():
                    translation = STRINGS[locale][key]
                    self.assertTrue(translation.strip(), (locale, key))
                    self.assertNotIn('\ufffd', translation, (locale, key))
                    self.assertEqual(placeholders(baseline), placeholders(translation), (locale, key))

    def test_each_help_section_is_translated(self):
        self.assertEqual(len(HELP_IDS), 7)
        for locale, _ in LANGUAGES:
            for key in HELP_IDS:
                self.assertTrue(tr(locale, 'help.' + key + '.title'))
                self.assertTrue(tr(locale, 'help.' + key + '.body'))

    def test_names_for_every_piece_and_selection(self):
        self.assertEqual(len(PIECE_IDS), 10)
        for locale, _ in LANGUAGES:
            self.assertNotEqual(piece_name(locale, 0), piece_name(locale, 1))
            self.assertEqual(piece_name(locale, 6), piece_name(locale, 9))
            self.assertEqual(selected_names(locale, ()), tr(locale, 'selection_none'))
            self.assertIn(piece_name(locale, 0), selected_names(locale, (0,)))
            self.assertIn(piece_name(locale, 8), selected_names(locale, (0, 8)))
            self.assertIn('2', selected_names(locale, (0, 8)))
            self.assertTrue(piece_name(locale, 6, tile=True))

    def test_dynamic_messages_and_board_translations(self):
        for locale, _ in LANGUAGES:
            self.assertIn('12', tr(locale, 'best', steps=12, time='00:34'))
            self.assertIn('00:34', tr(locale, 'win_message', steps=12, time='00:34'))
            self.assertIn('12', tr(locale, 'win_message', steps=12, time='00:34'))
            self.assertTrue(tr(locale, 'board_exit'))
            self.assertTrue(tr(locale, 'board_pause'))
            self.assertIn('0.4.0', tr(locale, 'window_title'))

    def test_translations_do_not_modify_core_rules(self):
        from huarongdao.core import PIECES
        from huarongdao.model import GameModel
        game = GameModel()
        positions = game.positions
        for locale, _ in LANGUAGES:
            self.assertEqual(len([piece_name(locale, i) for i in range(10)]), len(PIECES))
            self.assertEqual(positions, game.positions)
        self.assertEqual(game.steps, 0)


if __name__ == '__main__':
    unittest.main()
