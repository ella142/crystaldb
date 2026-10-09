from __future__ import annotations

import hashlib
from pathlib import Path

from scripts.deep_rescue_powbase_v1 import (
    ARCHIVES_DIR,
    EXCLUDED_FINALIZED_ENTRIES,
    build_review,
    write_outputs,
)


def _archive_hashes() -> dict[str, str]:
    return {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in ARCHIVES_DIR.glob("*.zip")
    }


def test_deep_rescue_scope_and_fixed_width_rule(tmp_path: Path) -> None:
    before = _archive_hashes()
    payload = build_review()
    records = payload["records"]
    after = _archive_hashes()

    assert len(records) == 73
    assert not {row["entry_id"] for row in records} & EXCLUDED_FINALIZED_ENTRIES
    assert {row["deeper_decision"] for row in records} == {
        "promote_verified",
        "retain_conditional",
    }
    assert sum(row["deeper_decision"] == "promote_verified" for row in records) == 71
    assert sum(row["deeper_decision"] == "retain_conditional" for row in records) == 2
    assert before == after

    by_id = {row["entry_id"]: row for row in records}
    assert by_id["137"]["deeper_decision"] == "promote_verified"
    assert by_id["137"]["expected_point_count"] == 3001
    assert by_id["137"]["observed_point_count"] == 3010
    assert by_id["137"]["trailing_zero_count"] == 9
    assert by_id["137"]["final_canonical_point_count"] == 3001
    assert by_id["137"]["source_container_type"] == "plain_text"

    assert by_id["114"]["deeper_decision"] == "retain_conditional"
    assert by_id["114"]["trailing_zero_count"] == 11
    assert by_id["114"]["row_width"] == 8
    assert by_id["36"]["deeper_decision"] == "retain_conditional"
    assert len(by_id["36"]["source_member_filenames"]) == 2

    write_outputs(
        payload,
        csv_output=tmp_path / "powbase_deep_rescue_v1.csv",
        summary_output=tmp_path / "powbase_deep_rescue_v1_summary.md",
    )
    assert (tmp_path / "powbase_deep_rescue_v1.csv").exists()
    assert (tmp_path / "powbase_deep_rescue_v1_summary.md").exists()
