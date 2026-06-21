import os
import unittest

from pocket_bot import config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self._old = os.environ.pop(config.SSID_ENV_VAR, None)

    def tearDown(self):
        if self._old is not None:
            os.environ[config.SSID_ENV_VAR] = self._old

    def test_get_ssid_raises_without_env_var(self):
        with self.assertRaises(RuntimeError):
            config.get_ssid()

    def test_get_ssid_returns_env_value(self):
        os.environ[config.SSID_ENV_VAR] = "abc123"
        self.assertEqual(config.get_ssid(), "abc123")

    def test_candle_window_covers_rsi_period(self):
        self.assertGreater(config.CANDLE_WINDOW, config.RSI_PERIOD)


if __name__ == "__main__":
    unittest.main()
