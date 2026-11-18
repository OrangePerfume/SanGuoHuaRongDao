import unittest

from huarongdao.core import (
    BOARD_W, BOARD_H, GOAL, PIECES, START, canonical, index_for_solver_move,
    occupied_by, shifted, shortest_path, valid, won,
)


class CoreTests(unittest.TestCase):
    def test_classic_board_is_valid_and_has_two_holes(self):
        self.assertEqual((BOARD_W, BOARD_H), (4, 5))
        self.assertEqual(len(PIECES), 10)
        self.assertEqual(sum(p.w * p.h for p in PIECES), 18)
        self.assertTrue(valid(START))
        self.assertFalse(won(START))
        self.assertEqual(GOAL, 13)

    def test_start_occupancy_and_holes(self):
        self.assertEqual(occupied_by(START, 1, 0), 0)
        self.assertEqual(occupied_by(START, 2, 2), 1)
        self.assertEqual(occupied_by(START, 0, 3), 4)
        self.assertIsNone(occupied_by(START, 1, 4))
        self.assertIsNone(occupied_by(START, 2, 4))
        self.assertIsNone(occupied_by(START, 9, 9))

    def test_invalid_board_rejected(self):
        self.assertFalse(valid(START[:-1]))
        self.assertFalse(valid((-1,) + START[1:]))
        self.assertFalse(valid((19,) + START[1:]))
        self.assertFalse(valid((0,) + START[1:]))

    def test_collisions_boundaries_and_bad_direction(self):
        self.assertIsNone(shifted(START, 0, 0, 1))
        self.assertIsNone(shifted(START, 6, -1, 0))
        self.assertIsNone(shifted(START, 8, -1, 0))
        self.assertIsNone(shifted(START, 8, 0, 1))
        self.assertIsNone(shifted(START, 8, 1, 1))
        self.assertIsNone(shifted(START, 20, 1, 0))
        self.assertIsNone(shifted(START, 8, 0, 0))
        self.assertIsNone(shifted(START, 8, 1, 0, 0))
        self.assertIsNone(shifted(START, 8, 1, 0, 10))

    def test_two_cells_is_legal_when_path_clear(self):
        # 左下角的兵可以横穿两个连续空位；这是有效的一次拖拽、两步移动。
        result = shifted(START, 8, 1, 0, 2)
        self.assertIsNotNone(result)
        self.assertEqual(result[8], 18)
        self.assertTrue(valid(result))
        self.assertIsNone(shifted(START, 8, 1, 0, 3))

    def test_cannot_jump_over_a_piece(self):
        # 左下兵移一格后，右下士兵占有横向的下一格。
        moved = shifted(START, 8, 1, 0)
        self.assertIsNotNone(moved)
        self.assertIsNone(shifted(moved, 8, 1, 0, 2))

    def test_shortest_path_has_116_legal_steps_and_wins(self):
        path = shortest_path(START)
        self.assertIsNotNone(path)
        self.assertEqual(len(path), 116)
        state = START
        for step in path:
            idx = index_for_solver_move(state, step)
            dx = step.target % 4 - step.source % 4
            dy = step.target // 4 - step.source // 4
            state = shifted(state, idx, dx, dy)
            self.assertIsNotNone(state)
            self.assertTrue(valid(state))
        self.assertTrue(won(state))
        self.assertEqual(shortest_path(state), [])

    def test_identical_sizes_are_equivalent_for_solver(self):
        swapped = list(START)
        swapped[6], swapped[7] = swapped[7], swapped[6]
        self.assertEqual(canonical(START), canonical(tuple(swapped)))


if __name__ == '__main__':
    unittest.main()
