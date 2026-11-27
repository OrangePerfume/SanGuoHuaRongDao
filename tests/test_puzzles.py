"""Regression checks for classic layouts, record isolation and puzzle switching."""
from pathlib import Path
from tempfile import TemporaryDirectory
import importlib.util
import unittest
from unittest.mock import patch

from huarongdao.core import START, valid, won, shortest_path, index_for_solver_move, canonical
from huarongdao.hint import next_move
from huarongdao.i18n import LANGUAGES, tr
from huarongdao.model import GameModel
from huarongdao.puzzles import PUZZLES, DEFAULT_PUZZLE
from huarongdao.records import RecordStore


class PuzzleTests(unittest.TestCase):
    def test_each_opening_is_distinct_legal_and_solvable(self):
        self.assertEqual(PUZZLES[DEFAULT_PUZZLE].positions, START)
        self.assertEqual(len(PUZZLES), 6)
        self.assertEqual(len({canonical(p.positions) for p in PUZZLES.values()}), len(PUZZLES))
        for puzzle in PUZZLES.values():
            with self.subTest(puzzle=puzzle.id):
                self.assertTrue(valid(puzzle.positions))
                self.assertFalse(won(puzzle.positions))
                path = shortest_path(puzzle.positions)
                self.assertEqual(len(path), puzzle.minimum_steps)
                game = GameModel()
                game.select_puzzle(puzzle.id)
                for move in path:
                    i = index_for_solver_move(game.positions, move)
                    self.assertEqual(game.move(i, move.target % 4 - move.source % 4,
                                               move.target // 4 - move.source // 4), 1)
                self.assertTrue(game.finished)
                self.assertEqual(game.steps, puzzle.minimum_steps)
                game.reset()
                self.assertEqual(game.positions, puzzle.positions)
                self.assertEqual(game.steps, 0)

    def test_switch_clears_history_timer_and_pause(self):
        game = GameModel()
        game.move(8, 1, 0)
        game.toggle_pause()
        game.select_puzzle('first_arrival')
        self.assertEqual(game.positions, PUZZLES['first_arrival'].positions)
        self.assertEqual(game.steps, 0)
        self.assertEqual(game.elapsed, 0)
        self.assertFalse(game.running)
        self.assertFalse(game.paused)
        self.assertFalse(game.undo())
        with self.assertRaises(ValueError):
            game.select_puzzle('invalid')
        self.assertEqual(game.puzzle_id, 'first_arrival')

    def test_hint_uses_actual_puzzle(self):
        for puzzle in PUZZLES.values():
            with self.subTest(puzzle=puzzle.id):
                hint = next_move(puzzle.positions)
                self.assertEqual(hint.remaining, puzzle.minimum_steps)
                game = GameModel()
                game.select_puzzle(puzzle.id)
                self.assertEqual(game.move(hint.piece, hint.dx, hint.dy), 1)
                self.assertEqual(game.positions[hint.piece], hint.target)

    def test_existing_classic_record_and_separate_records(self):
        with TemporaryDirectory() as td:
            directory = Path(td)
            legacy = RecordStore(directory / 'best.json')
            legacy.update_best(120, 420)
            classic = RecordStore.for_puzzle(directory, DEFAULT_PUZZLE)
            self.assertEqual(classic.load(), {'steps': 120, 'seconds': 420})
            for puzzle in PUZZLES.values():
                if puzzle.id == DEFAULT_PUZZLE:
                    continue
                store = RecordStore.for_puzzle(directory, puzzle.id)
                self.assertEqual(store.load(), {})
                store.update_best(puzzle.minimum_steps, 30)
                self.assertEqual(store.load()['steps'], puzzle.minimum_steps)
            self.assertEqual(classic.load(), {'steps': 120, 'seconds': 420})
            with self.assertRaises(ValueError):
                RecordStore.for_puzzle(directory, '../escape')

    def test_puzzle_translations_and_menu_labels(self):
        for language, _ in LANGUAGES:
            names = []
            for p in PUZZLES.values():
                name = tr(language, 'puzzle_' + p.id)
                names.append(name)
                self.assertIn(name, tr(language, 'puzzle_menu_item', name=name, steps=p.minimum_steps))
                self.assertIn(str(p.minimum_steps), tr(language, 'puzzle_minimum', steps=p.minimum_steps))
            self.assertEqual(len(set(names)), len(PUZZLES))


@unittest.skipUnless(importlib.util.find_spec('PySide6'), 'Requires PySide6 / Qt')
class PuzzleGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_switch_cancel_accept_and_restart(self):
        from huarongdao.gui import MainWindow
        win = MainWindow()
        try:
            with TemporaryDirectory() as td:
                win.record_directory = Path(td)
                win.records = RecordStore.for_puzzle(win.record_directory, DEFAULT_PUZZLE)
                win.records.update_best(120, 50)
                win.best = win.records.load()
                win._make_move(8, 1, 0, 1)
                before = (win.game.positions, win.game.steps, tuple(win.game.history), win.best)
                with patch.object(win, '_confirm_discard', return_value=False):
                    win.puzzle_actions['first_arrival'].trigger()
                self.assertEqual(before, (win.game.positions, win.game.steps, tuple(win.game.history), win.best))
                self.assertTrue(win.puzzle_actions['classic'].isChecked())
                with patch.object(win, '_confirm_discard', return_value=True):
                    win.puzzle_actions['first_arrival'].trigger()
                self.assertEqual(win.game.positions, PUZZLES['first_arrival'].positions)
                self.assertEqual(win.game.steps, 0)
                self.assertFalse(win.board._motion.starts)
                self.assertFalse(win.board._selected)
                self.assertIsNone(win.board.solution_hint)
                self.assertEqual(win.best, {})
                self.assertTrue(win.puzzle_actions['first_arrival'].isChecked())
                win._request_hint()
                self.assertIsNotNone(win.board.solution_hint)
                hint = win.board.solution_hint
                win._make_move(hint.piece, hint.dx, hint.dy, 1)
                with patch.object(win, '_confirm_discard', return_value=True):
                    win._restart()
                self.assertEqual(win.game.positions, PUZZLES['first_arrival'].positions)
                self.assertIsNone(win.board.solution_hint)
                self.assertTrue(win.select_puzzle('classic'))
                self.assertEqual(win.best, {'steps': 120, 'seconds': 50})
        finally:
            win.close()

    def test_all_locales_and_sizes_keep_current_puzzle(self):
        from huarongdao.gui import MainWindow
        win = MainWindow()
        try:
            win.select_puzzle('encirclement')
            win.show()
            for language, _ in LANGUAGES:
                win.set_language(language, persist=False)
                for size in ((990, 700), (1170, 840)):
                    win.resize(*size)
                    self.app.processEvents()
                    self.assertEqual(win.game.positions, PUZZLES['encirclement'].positions)
                    self.assertTrue(win.puzzle_actions['encirclement'].isChecked())
                    self.assertEqual(len(win.puzzle_menu.actions()), len(PUZZLES))
                    self.assertTrue(win.puzzle_button.isVisible())
                    self.assertEqual(win.puzzle_button.toolTip(), tr(language, 'puzzle_encirclement'))
                    self.assertEqual(win.side_scroll.horizontalScrollBar().maximum(), 0)
                    for label in (win.title_label, win.subtitle_label):
                        self.assertLessEqual(label.fontMetrics().horizontalAdvance(label.text()), label.contentsRect().width()+2)
                    self.assertFalse(win.grab().isNull())
        finally:
            win.close()
