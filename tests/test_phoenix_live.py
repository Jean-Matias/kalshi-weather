import unittest

from phoenix_live import build_phoenix_live_dashboard, phoenix_config


class PhoenixLiveDashboardTests(unittest.TestCase):
    def test_phoenix_config_uses_kphx_and_market_date(self):
        config = phoenix_config()

        self.assertEqual(config["city"], "Phoenix")
        self.assertEqual(config["station_id"], "KPHX")
        self.assertIn("market_date", config)

    def test_live_dashboard_polls_official_kphx_endpoints_and_draws_bucket_lines(self):
        html = build_phoenix_live_dashboard(
            {
                "city": "Phoenix",
                "station_id": "KPHX",
                "station_name": "Phoenix Sky Harbor International Airport",
                "market_date": "2026-05-28",
                "timezone": "America/Phoenix",
            }
        )

        self.assertIn("Phoenix Live Temperature", html)
        self.assertIn("api.weather.gov/stations/KPHX/observations/latest", html)
        self.assertIn("api.weather.gov/stations/KPHX/observations?", html)
        self.assertIn("setInterval(refresh, 60000)", html)
        self.assertIn("drawBucketLine(ctx, chart, 93", html)
        self.assertIn("drawBucketLine(ctx, chart, 94", html)
        self.assertIn("external-api.kalshi.com/trade-api/v2/events/KXHIGHTPHX-26MAY28", html)
        self.assertIn("Kalshi implied high", html)
        self.assertIn("drawKalshiLine(ctx, chart, kalshi.expectedTemp", html)
        self.assertIn("High so far", html)


if __name__ == "__main__":
    unittest.main()
