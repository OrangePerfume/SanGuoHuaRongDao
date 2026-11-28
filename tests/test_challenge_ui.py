"""Presentation integration helpers run even without Qt."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from huarongdao.challenge import ChallengeSpec, ChallengeSession
from huarongdao.challenge_records import ChallengeRecords
from huarongdao.challenge_ui import PreparationClock, archive_invalid_record, read_challenge_overview
from huarongdao.core import shortest_path, index_for_solver_move


class ChallengePresentationTests(unittest.TestCase):
    def test_prepare_clock_excludes_setup_but_never_pauses_after_start(self):
        now = [100.0]
        clock = PreparationClock(lambda: now[0])
        session = ChallengeSession(ChallengeSpec('classic', 'time', 'extreme'), clock)
        now[0] += 12.5
        self.assertEqual(session.elapsed, 0)
        clock.start()
        now[0] += 1.25
        clock.start()
        self.assertEqual(session.elapsed, 1.25)
        now[0] += session.spec.limit
        self.assertEqual(session.poll(), 'timeout')

    def test_overview_separates_missing_invalid_and_completed(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            spec = ChallengeSpec('first_arrival', 'steps', 'extreme')
            session = ChallengeSession(spec, lambda: 0.0)
            for move in shortest_path(session.game.positions):
                index = index_for_solver_move(session.game.positions, move)
                session.move((index,), move.target % 4 - move.source % 4,
                             move.target // 4 - move.source // 4)
            self.assertTrue(ChallengeRecords(root, spec).save_success(session))
            invalid = ChallengeSpec('classic', 'time', 'beginner')
            ChallengeRecords(root, invalid).path.write_bytes(b'invalid')
            records = dict(read_challenge_overview(root))
            self.assertEqual(len(records), 48)
            self.assertEqual(sum(bool(best) for best in records.values()), 1)
            self.assertEqual(records[spec]['steps'], 47)
            self.assertIsNone(records[invalid])
            self.assertEqual(records[ChallengeSpec('classic', 'time', 'extreme')], {})

    def test_archive_preserves_original_bytes_and_never_overwrites(self):
        with TemporaryDirectory() as td:
            store = ChallengeRecords(Path(td), ChallengeSpec('classic', 'time', 'extreme'))
            self.assertIsNone(archive_invalid_record(store))
            store.path.write_bytes(b'first invalid')
            first = archive_invalid_record(store)
            self.assertEqual(first.read_bytes(), b'first invalid')
            self.assertFalse(store.path.exists())
            store.path.write_bytes(b'second invalid')
            second = archive_invalid_record(store)
            self.assertNotEqual(first.parent, second.parent)
            self.assertEqual(second.read_bytes(), b'second invalid')
            self.assertEqual(first.read_bytes(), b'first invalid')

    def test_archive_failure_leaves_original_and_read_failure_is_not_corruption(self):
        with TemporaryDirectory() as td:
            store = ChallengeRecords(Path(td), ChallengeSpec('classic', 'time', 'extreme'))
            store.path.write_bytes(b'original')
            with patch('huarongdao.challenge_ui.os.replace', side_effect=PermissionError('denied')):
                with self.assertRaises(PermissionError):
                    archive_invalid_record(store)
            self.assertEqual(store.path.read_bytes(), b'original')
            with patch.object(store, 'load', side_effect=PermissionError('denied')):
                with self.assertRaises(PermissionError):
                    archive_invalid_record(store)
            self.assertEqual(store.path.read_bytes(), b'original')
            self.assertEqual(list(Path(td).iterdir()), [store.path])
