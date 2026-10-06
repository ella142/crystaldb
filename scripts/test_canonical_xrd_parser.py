from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crystaldb.sources.lab.canonical_xrd_parser import parse_canonical_xrd


def canonical_text(
    *,
    series: str = "null",
    point_count: str = "5",
    rows: str = (
        "5.000000 10\n"
        "5.010000 11\n"
        "5.020000 12\n"
        "5.030000 13\n"
        "5.040000 14\n"
    ),
) -> str:
    return (
        "# CrystalDB experimental powder XRD\n"
        "# format_version: 1.0\n"
        "# sample_id: LAB_SAM_000001\n"
        "# measurement_id: LAB_MEAS_000001\n"
        "# pattern_id: LAB_PAT_000001\n"
        "# source: lab\n"
        "# data_origin: experimental\n"
        "# modality: powder_xrd\n"
        "# contributor: JL\n"
        f"# source_series_label: {series}\n"
        "# source_sample_label: Example\n"
        "# nominal_element_ratio: Co3S4\n"
        "# phase_character: unknown\n"
        "# original_filename: Example.asc\n"
        "# original_relative_path: JL/Example.asc\n"
        "# original_sha256: rawhash\n"
        "# measurement_date: 2025-12-17 21:54\n"
        "# scan_axis: 2theta/theta\n"
        "# x_unit: degree\n"
        "# y_unit: counts\n"
        "# start_2theta_deg: 5.0\n"
        "# stop_2theta_deg: 5.04\n"
        "# step_2theta_deg: 0.01\n"
        f"# point_count: {point_count}\n"
        "# radiation_characteristic: K-ALPHA\n"
        "# wavelength_kalpha1_angstrom: 1.54059\n"
        "# wavelength_kalpha2_angstrom: 1.54441\n"
        "# voltage_kv: 40.0\n"
        "# current_ma: 30.0\n"
        "# detector: DteX250(H)\n"
        "# columns: two_theta_deg intensity_counts\n"
        + rows
    )


class CanonicalXrdParserTests(unittest.TestCase):
    def parse_text(self, text: str):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pattern.txt"
            path.write_text(text, encoding="utf-8", newline="")
            return parse_canonical_xrd(path)

    def test_parses_arrays_and_null_without_losing_unknown(self):
        result = self.parse_text(canonical_text())
        self.assertEqual(result.parse_status, "partial")
        self.assertIsNone(result.source_series_label)
        self.assertEqual(result.phase_character, "unknown")
        self.assertEqual(result.two_theta[:2], (5.0, 5.01))
        self.assertEqual(result.intensity, (10, 11, 12, 13, 14))
        self.assertTrue(result.qc["point_count_match"])
        self.assertTrue(result.qc["axis_consistent"])

    def test_count_mismatch_is_failed_without_repair(self):
        result = self.parse_text(canonical_text(point_count="6"))
        self.assertEqual(result.parse_status, "failed")
        self.assertEqual(len(result.two_theta), 5)
        self.assertTrue(
            any(
                warning.startswith("point_count_mismatch:")
                for warning in result.parse_warnings
            )
        )

    def test_decimal_intensity_keeps_numeric_semantics(self):
        result = self.parse_text(
            canonical_text(
                rows=(
                    "5.000000 10.5\n"
                    "5.010000 11.25\n"
                    "5.020000 12.0\n"
                    "5.030000 13.0\n"
                    "5.040000 14.0\n"
                )
            )
        )
        self.assertEqual(result.parse_status, "partial")
        self.assertEqual(result.intensity[0], 10.5)
        self.assertEqual(result.intensity[2], 12.0)


if __name__ == "__main__":
    unittest.main()
