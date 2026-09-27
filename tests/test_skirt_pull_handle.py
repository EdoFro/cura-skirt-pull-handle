import argparse
import json
import unittest
from pathlib import Path

from SkirtPullHandle import SkirtPullHandle, transform


FIXTURES = Path(__file__).parent / "fixtures"


def options(**overrides):
    values = {
        "add_early_handle": False,
        "connect_skirt_to_model": False,
        "anchor_spacing": 10.0,
        "min_chord": 5.0,
        "reach": 5.0,
        "height": 3.0,
        "segments": 24,
        "speed": 12.0,
        "fan_percent": 75.0,
        "landing_flow": 1.4,
        "max_connector_length": 30.0,
        "connector_speed": 20.0,
        "bed_min_x": 0.0,
        "bed_min_y": 0.0,
        "bed_max_x": 220.0,
        "bed_max_y": 220.0,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class TransformTests(unittest.TestCase):
    def load(self, name):
        return (FIXTURES / name).read_text(encoding="utf-8")

    def test_default_adds_one_top_handle_per_skirt(self):
        output, count, warnings = transform(self.load("box-x2-skirt.gcode"), options())
        self.assertEqual(count, 2)
        self.assertEqual(output.count(";SKIRT_HANDLE_BEGIN"), 2)
        self.assertFalse(warnings)

    def test_early_handle_and_connectors_for_sequential_print(self):
        output, count, warnings = transform(
            self.load("box-x2-skirt.gcode"),
            options(add_early_handle=True, connect_skirt_to_model=True),
        )
        self.assertEqual(count, 4)
        self.assertEqual(output.count(";SKIRT_HANDLE_BEGIN"), 4)
        self.assertEqual(output.count(";SKIRT_MODEL_CONNECTOR_BEGIN"), 2)
        self.assertFalse(warnings)

    def test_single_layer_does_not_duplicate_handle(self):
        output, count, warnings = transform(
            self.load("box-with-skirt.gcode"),
            options(add_early_handle=True, connect_skirt_to_model=True),
        )
        self.assertEqual(count, 1)
        self.assertEqual(output.count(";SKIRT_HANDLE_BEGIN"), 1)
        self.assertEqual(output.count(";SKIRT_MODEL_CONNECTOR_BEGIN"), 1)
        self.assertFalse(warnings)

    def test_cura_settings_have_required_properties(self):
        settings = json.loads(SkirtPullHandle().getSettingDataString())["settings"]
        required = {"label", "description", "type", "default_value"}
        for key, definition in settings.items():
            self.assertFalse(required - definition.keys(), key)


if __name__ == "__main__":
    unittest.main()
