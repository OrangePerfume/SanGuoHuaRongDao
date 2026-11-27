"""Challenge rules, deadline and independent bounded record regression tests."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from huarongdao.challenge import ChallengeSession, ChallengeSpec, DIFFICULTIES, MODES
from huarongdao.challenge_records import ChallengeRecords, InvalidChallengeRecord
from huarongdao.puzzles import PUZZLES
from huarongdao.core import shortest_path, index_for_solver_move


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def solve(session):
    for move in shortest_path(session.game.positions):
        index = index_for_solver_move(session.game.positions, move)
        if not session.move((index,), move.target % 4 - move.source % 4, move.target // 4 - move.source // 4):
            raise AssertionError('No legal solution')


class ChallengeTests(unittest.TestCase):
    def test_limits_all_puzzles(self):
        for puzzle in PUZZLES.values():
            for mode in MODES:
                limits = [ChallengeSpec(puzzle.id, mode, d).limit for d in DIFFICULTIES]
                self.assertEqual(limits, sorted(limits, reverse=True))
                self.assertGreater(limits[-1], 0)
            self.assertEqual(ChallengeSpec(puzzle.id, 'steps', 'extreme').limit, puzzle.minimum_steps)
        self.assertEqual(ChallengeSpec('classic', 'time', 'extreme').limit, 180)
        self.assertEqual(ChallengeSpec('classic', 'steps', 'expert').limit, 140)
        for args in [('bad', 'time', 'expert'), ('classic', 'bad', 'expert'), ('classic', 'time', 'bad')]:
            with self.assertRaises(ValueError):
                ChallengeSpec(*args)

    def test_deadline_includes_idle_and_blocks_move(self):
        clock = Clock()
        session = ChallengeSession(ChallengeSpec('classic', 'time', 'extreme'), clock)
        before = session.game.positions
        clock.now = 179.1
        self.assertEqual(session.remaining, 1)
        clock.now = 180
        self.assertEqual(session.move((8,), 1, 0), 0)
        self.assertEqual(session.status, 'timeout')
        self.assertEqual(session.game.positions, before)
        clock.now = 900
        self.assertEqual(session.elapsed, 180)

    def test_exact_step_cap_success(self):
        for puzzle in PUZZLES.values():
            with self.subTest(puzzle=puzzle.id):
                session = ChallengeSession(ChallengeSpec(puzzle.id, 'steps', 'extreme'), Clock())
                solve(session)
                self.assertEqual(session.status, 'success')
                self.assertEqual(session.game.steps, puzzle.minimum_steps)
                self.assertEqual(session.remaining, 0)
                self.assertEqual(session.move((0,), 0, 1), 0)

    def test_step_exhaustion_and_group_budget(self):
        session = ChallengeSession(ChallengeSpec('classic', 'steps', 'extreme'), Clock())
        session.game.steps = session.spec.limit - 1
        before = session.game.positions
        self.assertEqual(session.move((8, 9), 1, 0, 10), 0)
        self.assertEqual(session.game.positions, before)
        self.assertEqual(session.move((8,), 1, 0, 99), 1)
        self.assertEqual(session.status, 'exhausted')
        self.assertEqual(session.game.steps, session.spec.limit)

    def test_group_counts_per_piece(self):
        session = ChallengeSession(ChallengeSpec('classic', 'steps', 'beginner'), Clock())
        session.game.replace_for_test((9, 1, 0, 3, 8, 11, 5, 6, 16, 19))
        self.assertEqual(session.move((0, 6), 0, 1), 1)
        self.assertEqual(session.game.steps, 2)
        self.assertEqual(session.status, 'success')

    def test_deadline_beats_win_and_abandon_is_terminal(self):
        clock = Clock()
        session = ChallengeSession(ChallengeSpec('classic', 'time', 'extreme'), clock)
        session.game.replace_for_test((9, 1, 0, 3, 8, 11, 5, 6, 16, 19))
        clock.now = 180
        self.assertEqual(session.move((0,), 0, 1), 0)
        self.assertEqual(session.status, 'timeout')
        other = ChallengeSession(session.spec, clock)
        other.abandon()
        self.assertEqual(other.poll(), 'abandoned')
        self.assertEqual(other.move((8,), 1, 0), 0)

    def test_records_independent_rank_and_corrupt_preserved(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            spec = ChallengeSpec('first_arrival', 'time', 'beginner')
            clock = Clock()
            session = ChallengeSession(spec, clock)
            clock.now = 10
            solve(session)
            store = ChallengeRecords(root, spec)
            self.assertTrue(store.save_success(session))
            self.assertFalse(store.save_success(session))
            self.assertEqual(store.load(), {'steps': 47, 'milliseconds': 10000})
            self.assertEqual(ChallengeRecords(root, ChallengeSpec('first_arrival', 'steps', 'beginner')).load(), {})
            before = store.path.read_bytes()
            faster = ChallengeSession(spec, clock)
            clock.now += 5
            solve(faster)
            with patch('huarongdao.challenge_records.os.replace', side_effect=OSError('denied')):
                with self.assertRaises(OSError):
                    store.save_success(faster)
            self.assertEqual(store.path.read_bytes(), before)
            self.assertFalse(list(root.glob('*.tmp')))
            self.assertTrue(store.save_success(faster))
            store.path.write_bytes(b'broken')
            with self.assertRaises(InvalidChallengeRecord):
                store.save_success(session)
            self.assertEqual(store.path.read_bytes(), b'broken')
            with self.assertRaises(ValueError):
                store.save_success(ChallengeSession(spec, clock))
            store.path.write_text(json.dumps({'schema': 1, 'steps': True, 'milliseconds': 0}))
            with self.assertRaises(InvalidChallengeRecord):
                store.load()
            store.path.write_bytes(b'x' * 4097)
            with self.assertRaises(InvalidChallengeRecord):
                store.load()

    def test_invalid_moves(self):
        session = ChallengeSession(ChallengeSpec('classic', 'steps', 'beginner'), Clock())
        for indices, dx, dy, count in [((8, 8), 1, 0, 1), ((True,), 1, 0, 1), ((999,), 1, 0, 1), ((8,), 1, 1, 1), ((8,), 1, 0, True)]:
            self.assertEqual(session.move(indices, dx, dy, count), 0)
        self.assertEqual(session.game.steps, 0)
