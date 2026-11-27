"""Resume, bounded local storage, replay validation, and achievement counters."""
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from huarongdao.core import START, shortest_path, index_for_solver_move
from huarongdao.hint import next_move
from huarongdao.model import GameModel
from huarongdao.progress import (MAX_BYTES, InvalidProgress, Profile, ProgressStore,
                                 snapshot, restore_snapshot)
from huarongdao.records import RecordStore


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def solve(game, profile):
    for move in shortest_path(game.positions):
        i = index_for_solver_move(game.positions, move)
        game.move(i, move.target % 4 - move.source % 4, move.target // 4 - move.source // 4)
        profile.add(game.puzzle_id, 'moves')
    return profile.record_completion(game)


class ProgressTests(unittest.TestCase):
    def test_resume_restores_history_and_excludes_offline_time(self):
        clock = Clock()
        game = GameModel(clock=clock)
        self.assertEqual(game.move(8, 1, 0, 2), 2)
        clock.now += 15.5
        game.hint_count = 2
        game.undo()
        self.assertEqual(game.undo_count, 1)
        profile = Profile()
        profile.add('classic', 'moves', 2)
        profile.add('classic', 'undos')
        profile.add('classic', 'hints', 2)
        with TemporaryDirectory() as td:
            store = ProgressStore(Path(td) / 'progress.json')
            store.save(game, profile)
            clock.now += 900
            fresh = GameModel(clock=clock)
            restored = store.load(fresh)
            self.assertEqual(restored.stats, profile.stats)
            self.assertEqual(snapshot(fresh), json.loads(store.path.read_text())['active'])
            self.assertTrue(fresh.paused)
            self.assertFalse(fresh.running)
            self.assertEqual(fresh.elapsed, 15.5)
            self.assertEqual(fresh.move(8, 1, 0), 0)
            fresh.toggle_pause()
            clock.now += 3
            self.assertEqual(fresh.elapsed, 18.5)
            self.assertTrue(fresh.undo())
            self.assertEqual(fresh.positions, START)
            self.assertEqual(fresh.undo_count, 2)

    def test_nonclassic_and_group_history_round_trip(self):
        game = GameModel()
        game.select_puzzle('first_arrival')
        hint = next_move(game.positions)
        self.assertEqual(game.move(hint.piece, hint.dx, hint.dy), 1)
        restored = GameModel()
        restore_snapshot(restored, snapshot(game))
        self.assertEqual(restored.puzzle_id, 'first_arrival')
        self.assertEqual(restored.history, game.history)
        game.select_puzzle('classic')
        self.assertEqual(game.move(8, 1, 0), 1)
        self.assertEqual(game.move_group((8, 9), -1, 0), 1)
        restore_snapshot(restored, snapshot(game))
        self.assertEqual(restored.history_costs, [1, 2])
        restored.toggle_pause()
        self.assertTrue(restored.undo())
        self.assertEqual(restored.steps, 1)

    def test_invalid_snapshots_do_not_mutate_live_game(self):
        game = GameModel()
        game.move(8, 1, 0)
        good = snapshot(game)
        original = snapshot(GameModel())
        variants = [('puzzle', '../escape'), ('elapsed', float('nan')), ('elapsed', float('inf')),
                    ('elapsed', -1), ('steps', True), ('steps', 2), ('costs', [0]),
                    ('positions', [True] * 10), ('positions', list(START)),
                    ('history', [list(game.positions)]), ('history', [list(START)] * 20001),
                    ('completion_recorded', 1), ('hint_count', -1)]
        for key, value in variants:
            with self.subTest(key=key):
                bad = copy.deepcopy(good)
                bad[key] = value
                fresh = GameModel()
                with self.assertRaises(InvalidProgress):
                    restore_snapshot(fresh, bad)
                self.assertEqual(snapshot(fresh), original)
        # A legal destination is not proof of a legal history action.
        bad = copy.deepcopy(good)
        game.move(8, 1, 0)
        bad['positions'] = list(game.positions)
        with self.assertRaises(InvalidProgress):
            restore_snapshot(GameModel(), bad)

    def test_corrupt_future_and_oversized_files_preserved(self):
        with TemporaryDirectory() as td:
            path = Path(td) / 'progress.json'
            store = ProgressStore(path)
            self.assertEqual(store.load(GameModel()).stats, Profile().stats)
            for raw in (b'{broken', b'\xff', b'[' * 1500 + b']' * 1500,
                        b'{"schema":2}', b' ' * (MAX_BYTES + 1)):
                path.write_bytes(raw)
                with self.assertRaises(InvalidProgress):
                    store.load(GameModel())
                self.assertEqual(path.read_bytes(), raw)

    def test_atomic_failure_preserves_previous_file_and_removes_temp(self):
        with TemporaryDirectory() as td:
            path = Path(td) / 'progress.json'
            store = ProgressStore(path)
            game, profile = GameModel(), Profile()
            store.save(game, profile)
            old = path.read_bytes()
            game.move(8, 1, 0)
            with patch('huarongdao.progress.os.replace', side_effect=OSError('denied')):
                with self.assertRaises(OSError):
                    store.save(game, profile)
            self.assertEqual(path.read_bytes(), old)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_completion_counted_once_across_undo_reload_and_rewin(self):
        game, profile = GameModel(), Profile()
        game.select_puzzle('first_arrival')
        self.assertTrue(solve(game, profile))
        row = profile.stats['first_arrival']
        self.assertEqual((row['wins'], row['unassisted_wins'], row['optimal_wins']), (1, 1, 1))
        self.assertFalse(profile.record_completion(game))
        self.assertTrue(game.undo())
        with TemporaryDirectory() as td:
            store = ProgressStore(Path(td) / 'progress.json')
            store.save(game, profile)
            fresh = GameModel()
            profile = store.load(fresh)
            fresh.toggle_pause()
            self.assertFalse(solve(fresh, profile))
        self.assertEqual(profile.stats['first_arrival']['wins'], 1)
        fresh.reset()
        fresh.hint_count = 1
        self.assertTrue(solve(fresh, profile))
        row = profile.stats['first_arrival']
        self.assertEqual((row['wins'], row['unassisted_wins'], row['optimal_wins']), (2, 1, 1))
        self.assertEqual(profile.stats['classic']['wins'], 0)

    def test_old_score_retained_without_inventing_achievements(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            RecordStore.for_puzzle(root, 'classic').update_best(116, 240)
            game = GameModel()
            profile = ProgressStore(root / 'progress.json').load(game)
            self.assertEqual(profile.stats['classic']['wins'], 0)
            self.assertEqual(RecordStore.for_puzzle(root, 'classic').load(), {'steps': 116, 'seconds': 240})
