"""V0.2.0 棋子目标提示框：完整矩形而不是逐格提示。纯 Python 门禁。"""
import unittest

from huarongdao.core import (
    PIECES, START, BOARD_W, destination_footprints, display_hint_rectangles,
    legal_destinations, target_for_click, valid,
)


class HintGeometryTests(unittest.TestCase):
    def test_soldiers_use_one_by_one_footprints(self):
        hints = destination_footprints(START, (8,))
        self.assertEqual(len(hints), 2)
        self.assertEqual([rect for _, (rect,) in hints],
                         [(8, 1, 4, 1, 1), (8, 2, 4, 1, 1)])

    def test_vertical_general_uses_one_unbroken_rectangle(self):
        # 首步后马超可从 (0,2) 整体下移一格，目标为 (0,3) 的 1×2 矩形。
        state = (1, 9, 0, 3, 8, 11, 13, 14, 17, 19)
        self.assertTrue(valid(state))
        hints = destination_footprints(state, (4,))
        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0][1], ((4, 0, 3, 1, 2),))
        self.assertEqual(target_for_click(state, (4,), 0, 4), (0, 1, 1))

    def test_horizontal_general_uses_one_unbroken_rectangle(self):
        # 关羽整块向左移动；目标区域是 2×1，不是两个独立 1×1 框。
        state = (1, 9, 0, 3, 12, 11, 13, 14, 17, 19)
        self.assertTrue(valid(state))
        hints = destination_footprints(state, (1,))
        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0][1], ((1, 0, 2, 2, 1),))
        self.assertEqual(target_for_click(state, (1,), 0, 2), (-1, 0, 1))

    def test_caocao_uses_one_complete_two_by_two_square(self):
        # 沿真实可解棋局构造的一个中间局面：曹操可向右移动。
        state = (1, 9, 0, 11, 12, 14, 8, 19, 17, 13)
        self.assertTrue(valid(state))
        hints = destination_footprints(state, (0,))
        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0][1], ((0, 2, 0, 2, 2),))
        self.assertEqual(target_for_click(state, (0,), 3, 0), (1, 0, 1))
        self.assertEqual(target_for_click(state, (0,), 3, 1), (1, 0, 1))

    def test_multi_selection_preserves_whole_piece_shapes(self):
        # 同方向同格数移动，棋子彼此不碰撞；每个目标仍是一整块。
        state = (1, 9, 0, 3, 8, 11, 13, 14, 18, 19)
        self.assertTrue(valid(state))
        hints = destination_footprints(state, (8, 9))
        self.assertEqual(len(hints), 2)
        self.assertEqual(hints[0][1], ((8, 1, 4, 1, 1), (9, 2, 4, 1, 1)))
        self.assertEqual(hints[1][1], ((8, 0, 4, 1, 1), (9, 1, 4, 1, 1)))

    def test_only_legal_complete_destinations_appear(self):
        states_and_groups = (
            (START, (8,)),
            ((1, 9, 0, 3, 8, 11, 13, 14, 17, 19), (4,)),
            ((1, 9, 0, 3, 12, 11, 13, 14, 17, 19), (1,)),
            ((1, 9, 0, 11, 12, 14, 8, 19, 17, 13), (0,)),
        )
        for state, group in states_and_groups:
            for destination, footprints in destination_footprints(state, group):
                self.assertTrue(valid(destination.positions))
                self.assertEqual(len(footprints), len(group))
                for index, col, row, width, height in footprints:
                    self.assertEqual((width, height),
                                     (PIECES[index].w, PIECES[index].h))
                    self.assertEqual((col, row),
                                     (destination.positions[index] % BOARD_W,
                                      destination.positions[index] // BOARD_W))

    def test_overlapping_vertical_targets_are_one_three_cell_rectangle(self):
        state = (1, 16, 9, 11, 8, 10, 0, 4, 18, 19)
        self.assertTrue(valid(state))
        self.assertEqual(display_hint_rectangles(state, (3,)), ((3, 0, 1, 3),))
        self.assertEqual(target_for_click(state, (3,), 3, 1), (0, -1, 1))
        self.assertEqual(target_for_click(state, (3,), 3, 0), (0, -1, 2))

    def test_overlapping_horizontal_targets_are_one_three_cell_rectangle(self):
        state = (1, 16, 9, 3, 8, 11, 0, 4, 10, 14)
        self.assertTrue(valid(state))
        self.assertEqual(display_hint_rectangles(state, (1,)), ((1, 4, 3, 1),))
        self.assertEqual(target_for_click(state, (1,), 2, 4), (1, 0, 1))
        self.assertEqual(target_for_click(state, (1,), 3, 4), (1, 0, 2))

    def test_adjacent_soldier_targets_remain_separate(self):
        self.assertEqual(display_hint_rectangles(START, (8,)), ((1, 4, 1, 1), (2, 4, 1, 1)))

    def test_empty_and_invalid_selection_generate_no_hints(self):
        self.assertEqual(legal_destinations(START, ()), ())
        self.assertEqual(legal_destinations(START, (10,)), ())
        self.assertEqual(legal_destinations(START, (8, 8)), ())


if __name__ == '__main__':
    unittest.main()
