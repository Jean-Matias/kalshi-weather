import unittest

from pocket_bot import signals


class RsiTests(unittest.TestCase):
    def test_rsi_known_value(self):
        # closes -> diffs [2, -1, 2, 1, -2]; period=3 uses last 3 diffs [2, 1, -2]
        # avg_gain = (2+1)/3 = 1.0, avg_loss = 2/3 = 0.6667, rs = 1.5
        # rsi = 100 - 100/(1+1.5) = 60.0
        closes = [10.0, 12.0, 11.0, 13.0, 14.0, 12.0]
        self.assertAlmostEqual(signals.rsi(closes, period=3), 60.0, places=6)

    def test_rsi_all_gains_is_100(self):
        closes = [10.0, 11.0, 12.0, 13.0]
        self.assertEqual(signals.rsi(closes, period=3), 100.0)

    def test_rsi_raises_with_too_few_closes(self):
        with self.assertRaises(ValueError):
            signals.rsi([10.0, 11.0], period=3)


class SignalTests(unittest.TestCase):
    def test_overbought_returns_put(self):
        self.assertEqual(signals.signal(75.0, overbought=70.0, oversold=30.0), "put")

    def test_oversold_returns_call(self):
        self.assertEqual(signals.signal(25.0, overbought=70.0, oversold=30.0), "call")

    def test_boundary_overbought_is_inclusive(self):
        self.assertEqual(signals.signal(70.0, overbought=70.0, oversold=30.0), "put")

    def test_boundary_oversold_is_inclusive(self):
        self.assertEqual(signals.signal(30.0, overbought=70.0, oversold=30.0), "call")

    def test_neutral_returns_none(self):
        self.assertIsNone(signals.signal(50.0, overbought=70.0, oversold=30.0))


if __name__ == "__main__":
    unittest.main()
