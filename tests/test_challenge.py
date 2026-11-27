"""Challenge rules, deadline and independent bounded record regression tests."""
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from huarongdao.challenge import ChallengeSession, ChallengeSpec, DIFFICULTIES, MODES, RULE_VERSION
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
        for i in range(session.spec.limit - 1):
            self.assertEqual(session.move((8,), 1 if i % 2 == 0 else -1, 0), 1)
        before = session.game.positions
        self.assertEqual(session.move((8, 9), 1, 0, 10), 0)
        self.assertEqual(session.game.positions, before)
        self.assertEqual(session.move((8,), -1, 0, 99), 1)
        self.assertEqual(session.status, 'exhausted')
        self.assertEqual(session.game.steps, session.spec.limit)

    def test_group_counts_per_piece(self):
        session = ChallengeSession(ChallengeSpec('classic', 'steps', 'beginner'), Clock())
        self.assertEqual(session.move((8,), 1, 0), 1)
        self.assertEqual(session.move((8, 9), -1, 0), 1)
        self.assertEqual(session.game.steps, 3)
        self.assertEqual(session.status, 'active')
        self.assertEqual(session.game.history, [])

    def test_deadline_beats_win_and_abandon_is_terminal(self):
        clock = Clock()
        session = ChallengeSession(ChallengeSpec('classic', 'time', 'extreme'), clock)
        path = shortest_path(session.game.positions)
        for move in path[:-1]:
            index = index_for_solver_move(session.game.positions, move)
            self.assertEqual(session.move((index,), move.target % 4 - move.source % 4, move.target // 4 - move.source // 4), 1)
        move = path[-1]
        index = index_for_solver_move(session.game.positions, move)
        clock.now = 180
        self.assertEqual(session.move((index,), move.target % 4 - move.source % 4, move.target // 4 - move.source // 4), 0)
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
            store.path.write_text(json.dumps({**store._identity(), 'steps': True, 'milliseconds': 0}))
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

    def test_result_immutable_even_after_model_reset(self):
        clock = Clock()
        session = ChallengeSession(ChallengeSpec('first_arrival', 'time', 'extreme'), clock)
        clock.now = 4.123
        solve(session)
        result = session.result
        self.assertEqual(result.milliseconds, 4123)
        self.assertEqual(result.steps, 47)
        with self.assertRaises(FrozenInstanceError):
            result.steps = 1
        session.game.reset()
        clock.now += 1000
        self.assertEqual(session.status, 'success')
        self.assertIs(session.result, result)
        with TemporaryDirectory() as td:
            store = ChallengeRecords(Path(td), session.spec)
            self.assertTrue(store.save_success(session))
            self.assertFalse(store.save_success(session))
            self.assertEqual(store.load(), {'steps': 47, 'milliseconds': 4123})
        self.assertEqual(session.poll(), 'success')
        self.assertEqual(session.game.steps, 47)
        self.assertEqual(session.game.positions, result.positions)

    def test_external_mutation_abandons_active_session(self):
        for mutate in (lambda g: setattr(g, 'steps', 47),
                       lambda g: g.move(8, 1, 0),
                       lambda g: setattr(g, 'hint_count', 1),
                       lambda g: g.select_puzzle('first_arrival')):
            session = ChallengeSession(ChallengeSpec('classic', 'steps', 'beginner'), Clock())
            mutate(session.game)
            self.assertEqual(session.poll(), 'abandoned')
            self.assertEqual(session.result.steps, 0)
            self.assertEqual(session.game.positions, PUZZLES['classic'].positions)
            self.assertEqual(session.move((8,), 1, 0), 0)

    def test_deadline_one_millisecond_before_success(self):
        clock = Clock()
        clock.now = 1000.0
        spec = ChallengeSpec('first_arrival', 'time', 'extreme')
        session = ChallengeSession(spec, clock)
        clock.now += spec.limit - .001
        solve(session)
        self.assertEqual(session.status, 'success')
        self.assertEqual(session.result.milliseconds, spec.limit * 1000 - 1)
        self.assertEqual(session.remaining, 1)
        with TemporaryDirectory() as td:
            self.assertTrue(ChallengeRecords(Path(td), spec).save_success(session))

    def test_validation_crosses_deadline(self):
        from huarongdao.core import shifted_group
        clock = Clock()
        session = ChallengeSession(ChallengeSpec('classic', 'time', 'extreme'), clock)
        before = session.game.positions
        clock.now = 179.999
        def crossing(*args):
            clock.now = 180
            return shifted_group(*args)
        with patch('huarongdao.challenge.shifted_group', side_effect=crossing):
            self.assertEqual(session.move((8,), 1, 0), 0)
        self.assertEqual(session.status, 'timeout')
        self.assertEqual(session.game.positions, before)
        self.assertEqual(session.result.steps, 0)

    def test_clock_does_not_run_backwards(self):
        clock = Clock()
        session = ChallengeSession(ChallengeSpec('classic', 'time', 'extreme'), clock)
        clock.now = 10
        self.assertEqual(session.elapsed, 10)
        clock.now = 5
        self.assertEqual(session.elapsed, 10)
        self.assertEqual(session.remaining, 170)

    def test_record_identity_and_rule_version(self):
        spec = ChallengeSpec('first_arrival', 'time', 'beginner')
        session = ChallengeSession(spec, Clock())
        solve(session)
        with TemporaryDirectory() as td:
            root = Path(td)
            source = ChallengeRecords(root, spec)
            source.save_success(session)
            original = source.path.read_bytes()
            self.assertEqual(json.loads(original)['rule_version'], RULE_VERSION)
            for other in (ChallengeSpec('first_arrival', 'steps', 'beginner'),
                          ChallengeSpec('first_arrival', 'time', 'standard'),
                          ChallengeSpec('classic', 'time', 'beginner')):
                store = ChallengeRecords(root, other)
                store.path.write_bytes(original)
                with self.assertRaises(InvalidChallengeRecord):
                    store.load()
                self.assertEqual(store.path.read_bytes(), original)
            for field, bad in [('rule_version', 2), ('rule_version', True), ('schema', 1), ('schema', True)]:
                payload = json.loads(original)
                payload[field] = bad
                source.path.write_text(json.dumps(payload))
                with self.assertRaises(InvalidChallengeRecord):
                    source.load()
            with self.assertRaises(ValueError):
                ChallengeSpec('classic', 'time', 'beginner', 99)

    def test_long_session_does_not_accumulate_undo_history(self):
        session = ChallengeSession(ChallengeSpec('classic', 'time', 'beginner'), Clock())
        for i in range(4000):
            self.assertEqual(session.move((8,), 1 if i % 2 == 0 else -1, 0), 1)
        self.assertEqual(session.game.steps, 4000)
        self.assertEqual(session.game.history, [])
        self.assertEqual(session.game.history_costs, [])
        session.abandon()
        self.assertEqual(session.result.steps, 4000)

    def test_legal_group_final_move_and_step_limit(self):
        from huarongdao.core import shifted_group, won
        for difficulty in ('beginner', 'extreme'):
            session = ChallengeSession(ChallengeSpec('first_arrival', 'steps', difficulty), Clock())
            path = shortest_path(session.game.positions)
            for move in path[:-1]:
                index = index_for_solver_move(session.game.positions, move)
                self.assertEqual(session.move((index,), move.target % 4 - move.source % 4, move.target // 4 - move.source // 4), 1)
            move = path[-1]
            index = index_for_solver_move(session.game.positions, move)
            dx, dy = move.target % 4 - move.source % 4, move.target // 4 - move.source // 4
            group = next((index, j) for j in range(len(session.game.positions)) if j != index
                         and (after := shifted_group(session.game.positions, (index, j), dx, dy)) is not None and won(after))
            if difficulty == 'extreme':
                self.assertEqual(session.move(group, dx, dy), 0)
                self.assertEqual(session.move((index,), dx, dy), 1)
                self.assertEqual(session.result.steps, 47)
            else:
                self.assertEqual(session.move(group, dx, dy), 1)
                self.assertEqual(session.result.steps, 48)
            self.assertEqual(session.status, 'success')

    def test_record_duplicate_fields_rejected(self):
        spec = ChallengeSpec('first_arrival', 'time', 'beginner')
        with TemporaryDirectory() as td:
            store = ChallengeRecords(Path(td), spec)
            raw = json.dumps({**store._identity(), 'steps': 47, 'milliseconds': 0})
            raw = raw[:-1] + ', "steps": 47}'
            store.path.write_text(raw)
            with self.assertRaises(InvalidChallengeRecord):
                store.load()
            self.assertEqual(store.path.read_text(), raw)
