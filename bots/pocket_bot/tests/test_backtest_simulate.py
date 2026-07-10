import unittest

from pocket_bot.backtest.run import simulate


class SimulateTests(unittest.TestCase):
    def test_known_sequence_produces_expected_signals_and_pnl(self):
        # closes -> two RSI(3)/70/30 "put" signals (computed by hand):
        #   i=6: window [7,8,9,10] all gains -> rsi=100 -> put; cur=10, next=11 -> loss (-1)
        #   i=7: window [8,9,10,11] all gains -> rsi=100 -> put; cur=11, next=10 -> win (+0.92)
        closes = [10, 9, 8, 7, 8, 9, 10, 11, 10]
        result = simulate(
            "TEST", closes, period=3, overbought=70.0, oversold=30.0, payout=0.92, stake=1.0,
        )
        self.assertEqual(result["signals"], 2)
        self.assertEqual(result["wins"], 1)
        self.assertAlmostEqual(result["win_rate"], 0.5)
        self.assertAlmostEqual(result["pnl"], -0.08, places=6)

    def test_no_signals_when_rsi_stays_neutral(self):
        closes = [10.0, 10.1, 10.0, 10.1, 10.0, 10.1, 10.0]
        result = simulate(
            "TEST", closes, period=3, overbought=70.0, oversold=30.0, payout=0.92, stake=1.0,
        )
        self.assertEqual(result["signals"], 0)
        self.assertEqual(result["wins"], 0)
        self.assertEqual(result["win_rate"], 0.0)
        self.assertEqual(result["pnl"], 0.0)


if __name__ == "__main__":
    unittest.main()
