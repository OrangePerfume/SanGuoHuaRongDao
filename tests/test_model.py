from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from huarongdao.core import START, shortest_path, index_for_solver_move, won
from huarongdao.model import GameModel
from huarongdao.records import RecordStore


class FakeClock:
    def __init__(self):
        self.value = 100.

    def __call__(self):
        return self.value

    def advance(self, seconds: float):
        self.value += seconds


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.g = GameModel(clock=self.clock)

    def test_invalid_move_does_not_count_or_start_timer(self):
        self.assertEqual(self.g.move(0, 0, 1), 0)
        self.assertEqual(self.g.steps, 0)
        self.assertEqual(self.g.elapsed, 0)
        self.assertFalse(self.g.running)

    def test_two_cell_move_counts_two_and_undos_once(self):
        self.assertEqual(self.g.move(8, 1, 0, 2), 2)
        self.assertEqual(self.g.steps, 2)
        self.assertEqual(self.g.positions[8], 18)
        self.clock.advance(18)
        self.assertAlmostEqual(self.g.elapsed, 18)
        self.assertTrue(self.g.undo())
        self.assertEqual(self.g.positions[8], 17)
        self.assertEqual(self.g.steps, 1)
        self.assertAlmostEqual(self.g.elapsed, 18)
        self.assertTrue(self.g.undo())
        self.assertEqual(self.g.positions, START)
        self.assertEqual(self.g.elapsed, 0)
        self.assertFalse(self.g.undo())

    def test_pause_freezes_clock_and_blocks_movement(self):
        self.assertEqual(self.g.move(8, 1, 0), 1)
        self.clock.advance(8)
        self.assertTrue(self.g.toggle_pause())
        self.clock.advance(90)
        self.assertAlmostEqual(self.g.elapsed, 8)
        self.assertEqual(self.g.move(8, 1, 0), 0)
        self.assertFalse(self.g.undo())
        self.assertFalse(self.g.toggle_pause())
        self.clock.advance(4)
        self.assertAlmostEqual(self.g.elapsed, 12)

    def test_reset_clears_all_progress(self):
        self.g.move(8, 1, 0)
        self.g.reset()
        self.assertEqual(self.g.steps, 0)
        self.assertFalse(self.g.paused)
        self.assertEqual(self.g.positions, START)
        self.assertEqual(self.g.elapsed, 0)

    def test_win_freezes_timer_rejects_future_moves_then_undo(self):
        path = shortest_path(START)
        for step in path:
            idx = index_for_solver_move(self.g.positions, step)
            dx = step.target % 4 - step.source % 4
            dy = step.target // 4 - step.source // 4
            self.assertEqual(self.g.move(idx, dx, dy), 1)
            self.clock.advance(0.5)
        self.assertTrue(won(self.g.positions))
        self.assertTrue(self.g.finished)
        fixed = self.g.elapsed
        self.clock.advance(10)
        self.assertEqual(self.g.elapsed, fixed)
        self.assertEqual(self.g.move(0, 0, -1), 0)
        self.assertTrue(self.g.undo())
        self.assertFalse(self.g.finished)
        self.assertTrue(self.g.running)


class RecordTests(unittest.TestCase):
    def test_save_load_and_score_order(self):
        with TemporaryDirectory() as td:
            path=Path(td)/'records'/'best.json'
            store=RecordStore(path)
            self.assertEqual(store.load(),{})
            self.assertTrue(store.update_best(116, 450))
            self.assertEqual(store.load(),{'steps':116,'seconds':450})
            self.assertFalse(store.update_best(117, 100))
            self.assertFalse(store.update_best(116, 500))
            self.assertTrue(store.update_best(116, 400))
            self.assertEqual(store.load(),{'steps':116,'seconds':400})
            self.assertTrue(store.update_best(115, 900))
            self.assertEqual(store.load(),{'steps':115,'seconds':900})

    def test_corruption_and_invalid_data_do_not_crash(self):
        with TemporaryDirectory() as td:
            p=Path(td)/'best.json'
            p.write_text('{broken', encoding='utf-8')
            self.assertEqual(RecordStore(p).load(),{})
            p.write_text(json.dumps({'steps':True,'seconds':4}),encoding='utf-8')
            self.assertEqual(RecordStore(p).load(),{})
            with self.assertRaises(ValueError):
                RecordStore(p).update_best(-1,0)


if __name__=='__main__':
    unittest.main()
