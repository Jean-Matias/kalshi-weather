import unittest


class WeatherBotCoreTests(unittest.TestCase):
    def test_default_bot_is_paper_only_and_uses_confirmation_strategy(self):
        from weather_bot.core import DEFAULT_BOTS

        bot = DEFAULT_BOTS[0]

        self.assertEqual(bot.strategy_name, "low_weather_confirmed")
        self.assertFalse(bot.trading_enabled)
        self.assertEqual(bot.mode, "paper")

    def test_snapshot_contains_paper_trades_and_risk_gates(self):
        from weather_bot.core import DEFAULT_BOTS, build_bot_snapshot

        snapshot = build_bot_snapshot(DEFAULT_BOTS[0], days=30)

        self.assertEqual(snapshot["mode"], "paper")
        self.assertFalse(snapshot["trading_enabled"])
        self.assertIn("armed", snapshot)
        self.assertGreaterEqual(snapshot["backtest"]["event_days"], 1)
        self.assertIn("risk_gates", snapshot)
        self.assertTrue(any(gate["name"] == "Real order placement" for gate in snapshot["risk_gates"]))
        self.assertTrue(all(trade["status"] in {"won", "lost"} for trade in snapshot["paper_trades"]))

    def test_bot_control_updates_arm_state_and_contract_count(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from weather_bot.core import DEFAULT_BOTS, bot_summaries, update_bot_control

        bot = DEFAULT_BOTS[0]

        with TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "controls.json"
            updated = update_bot_control(bot.bot_id, armed=True, contracts=2, state_path=state_path)
            summaries = bot_summaries(state_path=state_path)

        self.assertTrue(updated.armed)
        self.assertEqual(updated.contracts, 2)
        self.assertTrue(summaries[0]["armed"])
        self.assertEqual(summaries[0]["contracts"], 2)
        self.assertFalse(summaries[0]["trading_enabled"])

    def test_bot_control_rejects_contracts_above_cap(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from weather_bot.core import DEFAULT_BOTS, update_bot_control

        bot = DEFAULT_BOTS[0]

        with TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "controls.json"
            with self.assertRaises(ValueError):
                update_bot_control(bot.bot_id, contracts=bot.max_contracts + 1, state_path=state_path)


class WeatherBotDashboardTests(unittest.TestCase):
    def test_dashboard_api_serves_bots_and_snapshot(self):
        from fastapi.testclient import TestClient
        from weather_bot.app import app

        client = TestClient(app)

        bots = client.get("/api/bots")
        snapshot = client.get("/api/bots/vegas-low-confirmation/snapshot?days=30")
        html = client.get("/")

        self.assertEqual(bots.status_code, 200)
        self.assertEqual(snapshot.status_code, 200)
        self.assertEqual(html.status_code, 200)
        self.assertIn("Weather Bot Command Center", html.text)
        self.assertEqual(snapshot.json()["mode"], "paper")

    def test_dashboard_renders_bot_control_inputs(self):
        from fastapi.testclient import TestClient
        from weather_bot.app import app

        client = TestClient(app)

        html = client.get("/")

        self.assertEqual(html.status_code, 200)
        self.assertIn('id="botArmed"', html.text)
        self.assertIn('id="contracts"', html.text)
        self.assertIn("Paper Bot Controls", html.text)

    def test_dashboard_api_updates_paper_bot_controls(self):
        from fastapi.testclient import TestClient
        from weather_bot.app import app

        client = TestClient(app)

        response = client.post(
            "/api/bots/vegas-low-confirmation/control",
            json={"armed": True, "contracts": 2},
        )
        snapshot = client.get("/api/bots/vegas-low-confirmation/snapshot?days=30")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["control"]["armed"])
        self.assertEqual(response.json()["control"]["contracts"], 2)
        self.assertFalse(response.json()["trading_enabled"])
        self.assertTrue(snapshot.json()["armed"])
        self.assertEqual(snapshot.json()["contracts"], 2)


if __name__ == "__main__":
    unittest.main()
