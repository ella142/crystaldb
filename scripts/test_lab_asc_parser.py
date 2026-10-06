from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crystaldb.sources.lab.asc_parser import parse_asc


def asc_text(
    counts: str = "10, 11, 12, 13\n14",
    *,
    start: str = "5",
    stop: str = "5.04",
    step: str = "0.01",
    count: str = "5",
    group_count: str = "1",
    extra_groups: str = "",
) -> str:
    return (
        "*TYPE = Raw\n"
        "*DATE = 17-Dec-25 21:54\n"
        "*GROUP_COUNT = " + group_count + "\n"
        "*SCAN_AXIS = 2theta/theta\n"
        "*XUNIT = deg.\n"
        "*YUNIT = counts\n"
        "*XRAY_CHAR = K-ALPHA\n"
        "*WAVE_LENGTH1 = 1.54059\n"
        "*BEGIN\n"
        "*GROUP = 0\n"
        f"*START = {start}\n"
        f"*STOP = {stop}\n"
        f"*STEP = {step}\n"
        "*KV = 40\n"
        "*MA = 30\n"
        f"*COUNT = {count}\n"
        f"{counts}\n"
        "*END\n"
        f"{extra_groups}"
        "*EOF\n"
    )


class AscParserTests(unittest.TestCase):
    def parse_text(self, text: str):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.asc"
            path.write_text(text, encoding="ascii", newline="")
            return parse_asc(path)

    def test_flattens_sequential_count_values_and_reconstructs_axis(self):
        result = self.parse_text(asc_text())
        self.assertEqual(result.parse_status, "ok")
        self.assertEqual(result.intensities, (10, 11, 12, 13, 14))
        self.assertEqual(result.two_theta, (5.0, 5.01, 5.02, 5.03, 5.04))
        self.assertTrue(result.canonicalizable)

    def test_count_mismatch_is_failed_without_repair(self):
        result = self.parse_text(asc_text(count="6"))
        self.assertEqual(result.parse_status, "failed")
        self.assertEqual(len(result.intensities), 5)
        self.assertEqual(len(result.two_theta), 6)
        self.assertFalse(result.canonicalizable)
        self.assertTrue(
            any("intensity_count_mismatch" in warning for warning in result.parse_warnings)
        )

    def test_inconsistent_scan_axis_is_failed(self):
        result = self.parse_text(asc_text(stop="5.05"))
        self.assertEqual(result.parse_status, "failed")
        self.assertFalse(result.canonicalizable)
        self.assertTrue(
            any("scan_count_inconsistent" in warning for warning in result.parse_warnings)
        )

    def test_multiple_groups_require_review(self):
        result = self.parse_text(
            asc_text(
                group_count="2",
                extra_groups="*BEGIN\n*GROUP = 1\n*COUNT = 2\n1, 2\n*END\n",
            )
        )
        self.assertEqual(result.parse_status, "failed")
        self.assertTrue(
            any("multi_group_requires_review" in warning for warning in result.parse_warnings)
        )


if __name__ == "__main__":
    unittest.main()
