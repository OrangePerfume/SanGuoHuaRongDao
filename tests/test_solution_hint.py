"""Next-move recommendations must preserve puzzle state and legal moves."""
import importlib.util
import unittest
from unittest.mock import patch

from huarongdao.core import START, shifted, shortest_path, valid
from huarongdao.hint import next_move, format_hint
from huarongdao.i18n import LANGUAGES, piece_name, tr
from huarongdao.model import GameModel

NEAR_WIN = (9, 1, 0, 3, 8, 11, 5, 6, 16, 19)


class SolutionHintTests(unittest.TestCase):
    def test_classic_start_recommends_a_legal_step_on_shortest_path(self):
        hint = next_move(START)
        self.assertIsNotNone(hint)
        self.assertEqual(hint.remaining, 116)
        self.assertEqual(START[hint.piece], hint.source)
        after = shifted(START, hint.piece, hint.dx, hint.dy)
        self.assertTrue(valid(after))
        self.assertEqual(after[hint.piece], hint.target)
        self.assertEqual(len(shortest_path(after)), hint.remaining - 1)

    def test_recompute_from_current_state_not_from_opening(self):
        game = GameModel()
        self.assertEqual(game.move(9, -1, 0), 1)
        before = (game.positions, game.steps, tuple(game.history), game.running)
        hint = next_move(game.positions)
        after = shifted(game.positions, hint.piece, hint.dx, hint.dy)
        self.assertEqual(after[hint.piece], hint.target)
        self.assertEqual(len(shortest_path(after)), hint.remaining - 1)
        self.assertEqual(before, (game.positions, game.steps, tuple(game.history), game.running))

    def test_near_win_and_completed_board(self):
        hint = next_move(NEAR_WIN)
        self.assertEqual((hint.piece, hint.dx, hint.dy, hint.remaining), (0, 0, 1, 1))
        finished = shifted(NEAR_WIN, hint.piece, hint.dx, hint.dy)
        self.assertIsNone(next_move(finished))

    def test_unsolvable_and_invalid_state(self):
        next_move.cache_clear()
        try:
            with patch('huarongdao.hint.shortest_path', return_value=None):
                self.assertIsNone(next_move(START))
        finally:
            next_move.cache_clear()
        with self.assertRaises(ValueError):
            next_move((0,)*10)

    def test_three_languages_include_actual_piece_location_and_direction(self):
        hint = next_move(START)
        for locale, _ in LANGUAGES:
            with self.subTest(locale=locale):
                message = format_hint(locale, hint)
                self.assertIn(piece_name(locale, hint.piece), message)
                self.assertIn(str(hint.source // 4 + 1), message)
                self.assertIn(str(hint.source % 4 + 1), message)
                self.assertEqual(format_hint(locale, None), tr(locale, 'solution_none'))


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'Requires PySide6 / Qt')
class SolutionHintGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from huarongdao.gui import MainWindow
        self.win = MainWindow()
        self.addCleanup(self.win.close)
        self.win.set_language('zh-CN', persist=False)
        self.win.show()
        self.app.processEvents()

    def test_button_is_advisory_and_can_clear_hint(self):
        win = self.win
        before = (win.game.positions, win.game.steps, tuple(win.game.history), win.game.running)
        win.board._selected = {9}
        win.board._emit_selection()
        win.hint_button.click()
        self.assertEqual(before, (win.game.positions, win.game.steps, tuple(win.game.history), win.game.running))
        self.assertEqual(win.board._selected, {9})
        self.assertTrue(win.board._targets_visible)
        self.assertEqual(win.board.solution_hint, next_move(win.game.positions))
        self.assertEqual(win.hint_button.text(), tr(win.language, 'solution_button'))
        self.assertTrue(win.clear_hint_button.isEnabled())
        self.assertEqual(win.hint_message.text(), format_hint(win.language, win.board.solution_hint))
        win.clear_hint_button.click()
        self.assertIsNone(win.board.solution_hint)
        self.assertFalse(win.clear_hint_button.isEnabled())
        self.assertEqual(win.hint_message.text(), tr(win.language, 'solution_idle'))
        self.assertEqual(win.footer_label.text(), tr(win.language, 'footer'))

    def test_hint_invalidates_on_move_undo_pause_and_reset(self):
        win = self.win
        win.hint_button.click()
        h = win.board.solution_hint
        win._make_move(h.piece, h.dx, h.dy, 1)
        self.assertIsNone(win.board.solution_hint)
        self.assertFalse(win.hint_button.isEnabled())
        win.board.clear_animation()
        self.assertTrue(win.hint_button.isEnabled())
        win.hint_button.click()
        win._pause()
        self.assertIsNone(win.board.solution_hint)
        self.assertFalse(win.hint_button.isEnabled())
        win._pause()
        win.hint_button.click()
        win._undo()
        self.assertIsNone(win.board.solution_hint)
        win.board.clear_animation()
        win.hint_button.click()
        win._restart()  # zero moves: no confirmation dialog
        self.assertIsNone(win.board.solution_hint)
        self.assertEqual(win.game.positions, START)

    def test_hint_render_and_layout_in_three_languages(self):
        win = self.win
        win.hint_button.click()
        suggestion = win.board.solution_hint
        for locale in ('zh-CN', 'zh-TW', 'en', 'zh-CN'):
            win.set_language(locale, persist=False)
            self.assertEqual(win.board.solution_hint, suggestion)
            self.assertEqual(win.hint_message.text(), format_hint(locale, suggestion))
            self.assertEqual(win.clear_hint_button.text(), tr(locale, 'solution_clear'))
            self.assertTrue(win.clear_hint_button.isEnabled())
            win.set_help_expanded(True)
            for size in ((990, 700), (1170, 840)):
                with self.subTest(locale=locale, size=size):
                    win.resize(*size)
                    self.app.processEvents()
                    self.assertFalse(win.grab().isNull())
                    for scroll in (win.side_scroll, win.help_scroll):
                        self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
                        self.assertLessEqual(scroll.widget().width(), scroll.viewport().width())
                    self.assertGreaterEqual(win.hint_button.width(), win.hint_button.minimumSizeHint().width())
                    self.assertTrue(win.footer_label.wordWrap())
                    self.assertGreaterEqual(win.footer_label.height()+2, win.footer_label.heightForWidth(win.footer_label.width()))
        self.assertEqual(win.game.steps, 0)
        self.assertFalse(win.game.running)
