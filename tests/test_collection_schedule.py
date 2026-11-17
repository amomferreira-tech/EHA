import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from collection_schedule import next_collection,is_stale


class CollectionScheduleTests(unittest.TestCase):
    @patch.dict('os.environ',COLLECT_MINUTE='20')
    def test_hourly_twenty_and_staleness(self):
        last=datetime(2026,11,17,13,20,tzinfo=timezone.utc)
        self.assertEqual(next_collection(last).hour,14)
        self.assertEqual(next_collection(last).minute,20)
        self.assertFalse(is_stale(last,datetime(2026,11,17,14,30,tzinfo=timezone.utc)))
        self.assertTrue(is_stale(last,datetime(2026,11,17,14,36,tzinfo=timezone.utc)))

    def test_midnight_and_startup_collection(self):
        with patch.dict('os.environ',COLLECT_MINUTE='20'):
            self.assertEqual(next_collection(datetime(2026,12,31,23,59,tzinfo=timezone.utc)),datetime(2027,1,1,0,20,tzinfo=timezone.utc))
            self.assertEqual(next_collection(datetime(2026,11,17,13,1,tzinfo=timezone.utc)).hour,13)
