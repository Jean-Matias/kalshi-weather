import unittest
from unittest.mock import patch

from scanner import _default_city_configs, _selected_city_configs, _skip_tomorrow


class ScannerConfigTests(unittest.TestCase):
    def test_selected_city_configs_filters_by_comma_separated_names(self):
        configs = [{"city": "Phoenix"}, {"city": "Oklahoma City"}, {"city": "Boston"}]

        with patch.dict("os.environ", {"KALSHI_CITIES": "phoenix, oklahoma city"}, clear=False):
            selected = _selected_city_configs(configs)

        self.assertEqual([config["city"] for config in selected], ["Phoenix", "Oklahoma City"])

    def test_skip_tomorrow_accepts_true_values(self):
        with patch.dict("os.environ", {"KALSHI_SKIP_TOMORROW": "true"}, clear=False):
            self.assertTrue(_skip_tomorrow())

    def test_default_city_configs_skips_coastal_risk_cities(self):
        configs = [
            {"city": "Phoenix", "coastal_risk": False},
            {"city": "Los Angeles", "coastal_risk": True},
        ]

        with patch.dict("os.environ", {}, clear=True):
            selected = _default_city_configs(configs)

        self.assertEqual([config["city"] for config in selected], ["Phoenix"])

    def test_explicit_city_filter_can_include_coastal_city(self):
        configs = [
            {"city": "Phoenix", "coastal_risk": False},
            {"city": "Los Angeles", "coastal_risk": True},
        ]

        with patch.dict("os.environ", {"KALSHI_CITIES": "Los Angeles"}, clear=True):
            selected = _default_city_configs(configs)

        self.assertEqual([config["city"] for config in selected], ["Los Angeles"])


if __name__ == "__main__":
    unittest.main()
