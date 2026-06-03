import unittest
from unittest.mock import patch

from scanner import _default_city_configs, _selected_city_configs


class ScannerConfigTests(unittest.TestCase):
    def test_selected_city_configs_filters_by_comma_separated_names(self):
        configs = [{"city": "Phoenix"}, {"city": "Oklahoma City"}, {"city": "Boston"}]

        with patch.dict("os.environ", {"KALSHI_CITIES": "phoenix, oklahoma city"}, clear=False):
            selected = _selected_city_configs(configs)

        self.assertEqual([config["city"] for config in selected], ["Phoenix", "Oklahoma City"])

    def test_default_city_configs_keeps_same_city_set(self):
        configs = [{"city": "Phoenix"}, {"city": "Oklahoma City"}]

        with patch.dict("os.environ", {}, clear=True):
            selected = _default_city_configs(configs)

        self.assertEqual([config["city"] for config in selected], ["Phoenix", "Oklahoma City"])


if __name__ == "__main__":
    unittest.main()
