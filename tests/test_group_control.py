"""点击目标空格与鼠标多选同向移动的规则、计步和原子撤销回归测试。"""
import unittest

from huarongdao.core import START, shifted_group, target_for_click, valid
from huarongdao.model import GameModel


class GroupMovesTests(unittest.TestCase):
    def test_click_moves_to_exact_empty_cell_with_multiple_steps(self):
        # 起点底部中央两个空格；从左下兵点击右侧第二个空格可滑动两格。
        self.assertEqual(target_for_click(START, (8,), 2, 4), (1, 0, 2))
        game = GameModel()
        self.assertEqual(game.move(8, 1, 0, 2), 2)
        self.assertEqual(game.positions[8], 18)
        self.assertEqual(game.steps, 2)

    def test_click_invalid_or_occupied_is_noop(self):
        self.assertIsNone(target_for_click(START, (0,), 1, 4))
        self.assertIsNone(target_for_click(START, (8,), 0, 3))
        self.assertIsNone(target_for_click(START, (8,), 0, 4))
        self.assertIsNone(target_for_click(START, (8,), 4, 4))
        self.assertIsNone(target_for_click(START, (), 1, 4))

    def test_group_translation_can_use_other_members_old_cells(self):
        # 兵8和兵9初始间隔两个空格；整体左移/右移均有边界约束。
        self.assertIsNone(shifted_group(START, (8, 9), 1, 0))
        self.assertIsNone(shifted_group(START, (8, 9), -1, 0))
        # 底部左兵先右移，再向右移动该两兵仍受到最右边界限制。
        game = GameModel()
        game.move(8, 1, 0, 2)
        # 组员在第 4 行的 (2,4) 与 (3,4)；整体左移后到 (1,4) 与 (2,4)。
        after = shifted_group(game.positions, (8, 9), -1, 0)
        self.assertIsNotNone(after)
        self.assertTrue(valid(after))
        self.assertEqual(after[8:10], (17, 18))

    def test_group_rejects_collisions_and_never_partially_commits(self):
        game = GameModel()
        start = game.positions
        self.assertEqual(game.move_group((8, 9), 1, 0), 0)
        self.assertEqual(game.positions, start)
        self.assertEqual(game.steps, 0)
        self.assertFalse(game.running)
        self.assertIsNone(shifted_group(START, (8, 8), 1, 0))
        self.assertIsNone(shifted_group(START, (8, 11), 1, 0))
        self.assertIsNone(shifted_group(START, (), 1, 0))
        self.assertIsNone(shifted_group(START, (8,), 1, 1))
        self.assertIsNone(shifted_group(START, (8,), 1, 0, 0))

    def test_group_cost_and_single_undo_are_atomic(self):
        game = GameModel()
        game.move(8, 1, 0, 2)
        before = game.positions
        self.assertEqual(game.move_group((8, 9), -1, 0), 1)
        self.assertEqual(game.steps, 4)  # 2 original moves + 2 pieces × 1 cell
        self.assertEqual(len(game.history), 3)
        self.assertEqual(game.history_costs, [1, 1, 2])
        self.assertTrue(game.undo())
        self.assertEqual(game.positions, before)
        self.assertEqual(game.steps, 2)
        self.assertTrue(game.undo())
        self.assertEqual(game.steps, 1)
        self.assertTrue(game.undo())
        self.assertEqual(game.positions, START)
        self.assertEqual(game.steps, 0)

    def test_group_drag_stops_at_last_reachable_position_and_undoes_once(self):
        game = GameModel()
        self.assertEqual(game.move(8, 1, 0, 2), 2)
        prior = game.positions
        self.assertEqual(game.move_group((8, 9), -1, 0, 6), 2)
        self.assertEqual(game.positions[8:10], (16, 17))
        self.assertEqual(game.steps, 6)  # 两枚棋子 × 两格 + 原有两步
        self.assertTrue(valid(game.positions))
        self.assertTrue(game.undo())
        self.assertEqual(game.positions, prior)
        self.assertEqual(game.steps, 2)

    def test_mixed_select_group_and_pause(self):
        game = GameModel()
        game.move(8, 1, 0, 2)
        self.assertTrue(game.toggle_pause())
        before = game.positions
        self.assertEqual(game.move_group((8, 9), -1, 0), 0)
        self.assertEqual(game.positions, before)
        game.toggle_pause()
        self.assertEqual(game.move_group((8, 9), -1, 0), 1)
        game.reset()
        self.assertEqual(game.history_costs, [])
        self.assertEqual(game.steps, 0)
        self.assertEqual(game.positions, START)

    def test_click_group_uses_same_direction(self):
        game = GameModel()
        game.move(8, 1, 0, 2)
        # 点击空出的 (1,4)，两枚底部士兵一起左移 1 格。
        move = target_for_click(game.positions, (8, 9), 1, 4)
        self.assertEqual(move, (-1, 0, 1))
        self.assertEqual(game.move_group((8, 9), *move), 1)
        self.assertEqual(game.positions[8:10], (17, 18))
        self.assertTrue(valid(game.positions))


if __name__ == '__main__':
    unittest.main()
