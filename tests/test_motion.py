"""V0.3.0 animation continuity, reversibility, speed presets (no Qt needed)."""
import unittest

from huarongdao.motion import ANIMATION_DURATIONS_MS, MotionTrack


class MotionTrackTests(unittest.TestCase):
    def setUp(self):
        self.track = MotionTrack()
        self.initial = (16, 18)

    def test_normal_animation_moves_between_grid_coordinates(self):
        self.assertTrue(self.track.retarget({0: 16}, (17, 18)))
        self.assertEqual(self.track.displayed(0, (17, 18)), (0.0, 4.0))
        self.track.set_progress(.5)
        self.assertEqual(self.track.displayed(0, (17, 18)), (.5, 4.0))
        self.track.complete()
        self.assertEqual(self.track.displayed(0, (17, 18)), (1.0, 4.0))

    def test_back_to_back_moves_start_at_current_visual_position(self):
        self.track.retarget({0: 16}, (17, 18))
        self.track.set_progress(.4)
        before = self.track.displayed(0, (17, 18))
        self.assertTrue(self.track.retarget({0: 17}, (18, 18)))
        self.assertEqual(self.track.displayed(0, (18, 18)), before)
        self.track.set_progress(.5)
        self.assertAlmostEqual(self.track.displayed(0, (18, 18))[0], 1.2)

    def test_undo_while_animation_running_has_no_jump(self):
        self.track.retarget({0: 16}, (18, 19))
        self.track.set_progress(.75)
        before = self.track.displayed(0, (18, 19))
        self.track.retarget({0: 18}, (16, 19))
        self.assertEqual(before, self.track.displayed(0, (16, 19)))
        self.track.set_progress(1.0)
        self.assertEqual(self.track.displayed(0, (16, 19)), (0.0, 4.0))

    def test_group_motion_and_unrelated_piece_continuity(self):
        self.track.retarget({0: 16, 1: 19}, (17, 18))
        self.track.set_progress(.5)
        other_was = self.track.displayed(1, (17, 18))
        self.track.retarget({0: 17}, (18, 18))
        self.assertEqual(self.track.displayed(1, (18, 18)), other_was)
        self.assertEqual(self.track.displayed(0, (18, 18)), (.5, 4.0))

    def test_retarget_can_finish_immediately_when_returning_to_initial_frame(self):
        self.track.retarget({0: 16}, (17, 18))
        self.assertFalse(self.track.retarget({0: 17}, (16, 18)))
        self.assertEqual(self.track.displayed(0, (16, 18)), (0.0, 4.0))

    def test_reset_disables_old_animation(self):
        self.track.retarget({0: 16}, (17, 18))
        self.track.complete()
        self.assertFalse(self.track.starts)
        self.assertFalse(self.track.targets)
        self.assertEqual(self.track.progress, 1.0)

    def test_progress_is_clamped(self):
        self.track.retarget({0: 16}, (17, 18))
        self.track.set_progress(3.0)
        self.assertEqual(self.track.displayed(0, (17, 18)), (1.0, 4.0))
        self.track.set_progress(-1.0)
        self.assertEqual(self.track.displayed(0, (17, 18)), (0.0, 4.0))

    def test_three_speed_presets(self):
        self.assertEqual(tuple(ANIMATION_DURATIONS_MS), ('slow', 'normal', 'fast'))
        self.assertGreater(ANIMATION_DURATIONS_MS['slow'], ANIMATION_DURATIONS_MS['normal'])
        self.assertGreater(ANIMATION_DURATIONS_MS['normal'], ANIMATION_DURATIONS_MS['fast'])


if __name__ == '__main__':
    unittest.main()
