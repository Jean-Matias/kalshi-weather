import unittest

from pocket_bot.backtest.data import _dedupe_consecutive, merge_history


class MergeHistoryTests(unittest.TestCase):
    def test_new_bars_are_added_and_counted(self):
        existing = {100: 1.10, 200: 1.11}
        fetched = {200: 1.115, 300: 1.12}  # 200 overlaps (newer value wins), 300 is new
        merged, new_count = merge_history(existing, fetched)
        self.assertEqual(new_count, 1)
        self.assertEqual(merged, {100: 1.10, 200: 1.115, 300: 1.12})

    def test_no_new_bars_returns_zero(self):
        existing = {100: 1.10, 200: 1.11}
        merged, new_count = merge_history(existing, dict(existing))
        self.assertEqual(new_count, 0)
        self.assertEqual(merged, existing)


class DedupeConsecutiveTests(unittest.TestCase):
    def test_collapses_runs_of_identical_closes(self):
        self.assertEqual(_dedupe_consecutive([1.0, 1.0, 1.0, 2.0, 2.0, 1.0]), [1.0, 2.0, 1.0])

    def test_empty_input(self):
        self.assertEqual(_dedupe_consecutive([]), [])


if __name__ == "__main__":
    unittest.main()
