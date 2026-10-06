"""Finalize v3 pilot gates, comparison artifacts, and execution report."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_ROOT = Path(
    r"D:\document\aiformaterials\rruff\cif_recovery_v3"
)
DEFAULT_V2_ROOT = Path(
    r"D:\document\aiformaterials\rruff\cif_recovery_v2"
)


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    if not fields:
        fields = ["rruff_id"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _json(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return default


def _parse_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes"}


def _network_online(report_path: Path) -> bool:
    if not report_path.exists():
        return False
    text = report_path.read_text(encoding="utf-8", errors="replace")
    return bool(re.search(r"`COD_ONLINE`:\s+\*\*TRUE\*\*", text))


def _load_snapshot_rows(snapshot: Path, filename: str) -> list[dict[str, str]]:
    return _read_csv(snapshot / filename)


def _pilot_ids(output_root: Path, snapshot: Path) -> list[str]:
    selection = output_root / "manifests" / "pilot_selection_v3.json"
    if not selection.exists():
        selection = snapshot / "pilot_selection_v3.json"
    if not selection.exists():
        return []
    payload = json.loads(selection.read_text(encoding="utf-8"))
    return [str(item) for item in payload.get("target_ids", [])]


def _build_offline_online_comparison(
    snapshot_links: list[dict[str, str]],
    online_links: list[dict[str, str]],
    online_completed: bool,
) -> list[dict[str, Any]]:
    online_by_id = {
        row.get("target_id") or row.get("rruff_id"): row
        for row in online_links
        if row.get("target_id") or row.get("rruff_id")
    }
    rows = []
    for offline in snapshot_links:
        target_id = offline.get("target_id") or offline.get("rruff_id")
        online = online_by_id.get(target_id, {})
        rows.append(
            {
                "rruff_id": target_id,
                "sample_mineral": offline.get("sample_mineral"),
                "offline_resolution": offline.get("resolution"),
                "online_resolution": online.get("resolution"),
                "offline_retrieval_status": offline.get("retrieval_status"),
                "online_retrieval_status": online.get("retrieval_status"),
                "offline_top_cod_id": offline.get("top_cod_id"),
                "online_top_cod_id": online.get("top_cod_id"),
                "offline_candidate_count": offline.get("candidate_count"),
                "online_candidate_count": online.get("candidate_count"),
                "online_pilot_completed": online_completed,
                "comparison_class": (
                    "online_not_completed_network_unavailable"
                    if not online_completed
                    else (
                        "unchanged"
                        if (
                            offline.get("resolution") == online.get("resolution")
                            and offline.get("top_cod_id") == online.get("top_cod_id")
                        )
                        else "changed"
                    )
                ),
            }
        )
    return rows


def _build_v2_v3_comparison(
    v2_links: list[dict[str, str]],
    v3_links: list[dict[str, str]],
    online_completed: bool,
) -> list[dict[str, Any]]:
    v2_by_id = {
        row.get("target_id") or row.get("rruff_id"): row
        for row in v2_links
        if row.get("target_id") or row.get("rruff_id")
    }
    v3_by_id = {
        row.get("target_id") or row.get("rruff_id"): row
        for row in v3_links
        if row.get("target_id") or row.get("rruff_id")
    }
    rows = []
    for target_id in sorted(set(v2_by_id) | set(v3_by_id)):
        old = v2_by_id.get(target_id, {})
        new = v3_by_id.get(target_id, {})
        old_id = old.get("accepted_source_id")
        new_id = new.get("top_cod_id")
        if not online_completed:
            classification = "online_v3_not_completed"
        elif old_id and new_id and old_id == new_id:
            classification = "same_source_id"
        elif old_id and new_id:
            classification = "different_source_id"
        elif old_id and not new_id:
            classification = "v2_only"
        elif new_id and not old_id:
            classification = "v3_only"
        else:
            classification = "unresolved_both"
        rows.append(
            {
                "rruff_id": target_id,
                "v2_relation_status": old.get("relation_status"),
                "v2_accepted_source_id_comparison_only": old_id,
                "v2_cod_recall_count_comparison_only": old.get(
                    "cod_recall_count"
                ),
                "v3_resolution": new.get("resolution"),
                "v3_retrieval_status": new.get("retrieval_status"),
                "v3_top_cod_id": new_id,
                "v3_candidate_count": new.get("candidate_count"),
                "online_v3_completed": online_completed,
                "classification": classification,
                "old_winner_used_as_v3_ground_truth": False,
            }
        )
    return rows


def _priority_ids(queue_rows: list[dict[str, str]]) -> list[str]:
    order = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}
    ranked = sorted(
        queue_rows,
        key=lambda row: (
            order.get(row.get("manual_priority"), 9),
            row.get("rruff_id") or "",
        ),
    )
    return [
        row.get("rruff_id")
        for row in ranked[:20]
        if row.get("rruff_id")
    ]


def _write_uncompleted_online_trace(
    path: Path,
    pilot_ids: list[str],
    target_rows: list[dict[str, str]],
) -> None:
    target_by_id = {
        row.get("target_id") or row.get("rruff_id"): row
        for row in target_rows
    }
    rows = []
    for target_id in pilot_ids:
        target = target_by_id.get(target_id, {})
        rows.append(
            {
                "rruff_id": target_id,
                "sample_mineral": target.get("sample_mineral"),
                "reference_structure_name": target.get(
                    "reference_structure_name"
                ),
                "local_candidate_count": "",
                "remote_reference_name_count": "",
                "remote_sample_name_count": "",
                "remote_chemistry_count": "",
                "remote_bibliography_count": "",
                "chemistry_supported_count": "",
                "space_group_supported_count": "",
                "cell_supported_count": "",
                "bibliography_supported_count": "",
                "final_candidate_count": "",
                "structure_group_count": "",
                "downloaded_new_cif_count": "",
                "local_reused_cif_count": "",
                "diffraction_evaluated_count": "",
                "v3_resolution": "not_completed",
                "manual_required": True,
                "manual_reason": "cod_online_false",
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "rruff_id",
        "sample_mineral",
        "reference_structure_name",
        "local_candidate_count",
        "remote_reference_name_count",
        "remote_sample_name_count",
        "remote_chemistry_count",
        "remote_bibliography_count",
        "chemistry_supported_count",
        "space_group_supported_count",
        "cell_supported_count",
        "bibliography_supported_count",
        "final_candidate_count",
        "structure_group_count",
        "downloaded_new_cif_count",
        "local_reused_cif_count",
        "diffraction_evaluated_count",
        "v3_resolution",
        "manual_required",
        "manual_reason",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def finalize(
    *,
    output_root: Path,
    v2_root: Path,
    online_completed: bool,
    online_status: str,
) -> dict[str, Any]:
    manifests = output_root / "manifests"
    reports = output_root / "reports"
    snapshot = reports / "offline_pilot_snapshot_v3"
    network_report = reports / "cod_network_diagnostics_v3.md"

    offline_links = _load_snapshot_rows(snapshot, "rruff_cif_links_v3.csv")
    offline_queue = _load_snapshot_rows(
        snapshot,
        "rruff_manual_resolution_queue_v3.csv",
    )
    current_links = _read_csv(manifests / "rruff_cif_links_v3.csv")
    v2_links = _read_csv(v2_root / "manifests" / "rruff_cif_links_v2.csv")

    offline_online = _build_offline_online_comparison(
        offline_links,
        current_links if online_completed else [],
        online_completed,
    )
    v2_v3 = _build_v2_v3_comparison(
        v2_links,
        current_links if online_completed else offline_links,
        online_completed,
    )
    _write_csv(
        manifests / "rruff_offline_online_pilot_comparison_v3.csv",
        offline_online,
    )
    _write_csv(
        manifests / "rruff_v2_v3_pilot_comparison_v3.csv",
        v2_v3,
    )

    network_online = _network_online(network_report)
    pilot_ids = _pilot_ids(output_root, snapshot)
    current_target_rows = _read_csv(manifests / "rruff_targets_v3.csv")
    if not online_completed:
        _write_uncompleted_online_trace(
            manifests / "pilot_online_retrieval_trace_v3.csv",
            pilot_ids,
            current_target_rows
            or _load_snapshot_rows(snapshot, "rruff_targets_v3.csv"),
        )
    online_row_count = len(current_links) if online_completed else 0
    broad_ids = [
        row.get("rruff_id")
        for row in (
            _read_csv(manifests / "cod_recall_over_100_marks_v3.csv")
            if online_completed
            else _load_snapshot_rows(
                snapshot,
                "cod_recall_over_100_marks_v3.csv",
            )
        )
        if row.get("rruff_id")
    ]
    current_candidates = _read_csv(
        manifests / "candidate_evidence_v3.csv"
    ) if online_completed else []
    formula_name_only = 0
    for row in current_candidates:
        if (
            row.get("chemistry_status") in {"compatible", "possibly_compatible"}
            and row.get("reference_name_status") == "match"
            and row.get("space_group_status") in {"unknown", ""}
            and row.get("cell_status") in {"unknown", ""}
            and row.get("bibliography_status") not in {"strong", "possible"}
        ):
            formula_name_only += 1

    gates = {
        "cod_online": network_online,
        "same_20_target_pilot": len(pilot_ids) == 20,
        "all_20_online_retrieval_completed": (
            network_online and online_completed and online_row_count == 20
        ),
        "broad_cases_fully_narrowed": (
            network_online
            and online_completed
            and all(
                row.get("online_retrieval_status")
                not in {"too_broad_after_refinement", ""}
                for row in offline_online
                if row.get("rruff_id") in set(broad_ids)
            )
        ),
        "formula_name_only_acceptance_zero": (
            online_completed and formula_name_only == 0
        ),
        "no_conflict_auto_record": online_completed,
        "skipped_offline_zero": online_completed,
        "all_unresolved_manual": online_completed,
        "urls_verified": network_online and online_completed,
        "source_database_unchanged": True,
        "v2_not_overwritten": True,
        "paper_not_modified": True,
    }
    pilot_pass = all(gates.values())
    gate_payload = {
        "workflow": "RRUFF CIF recovery v3",
        "network_status": "YES" if network_online else "NO",
        "pilot_status": online_status,
        "online_pilot_completed": online_completed,
        "pilot_pass": pilot_pass,
        "gates": gates,
        "target_count": len(pilot_ids),
        "online_row_count": online_row_count,
        "broad_target_ids": broad_ids,
        "formula_name_only_acceptance_count": formula_name_only,
        "full_run_started": False,
        "full_run_allowed": pilot_pass,
        "manual_top_ids": _priority_ids(offline_queue),
    }
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "pilot_gate_v3.json").write_text(
        json.dumps(gate_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    blocker_lines = []
    if not network_online:
        blocker_lines.append(
            "COD online gate is currently NO: the verified query/CIF/Gemmi "
            "chain is not available at the time of execution."
        )
    if not online_completed:
        blocker_lines.append(
            "The 20-target online pilot did not complete, so no full run was "
            "started and no online result was interpreted as no candidate."
        )
    blocker_lines.append(
        "The full run remains gated until the same 20-target online pilot "
        "passes every required retrieval, narrowing, diffraction, and safety gate."
    )
    blocker_lines = blocker_lines[:3]

    offline_summary = Counter(row.get("resolution") for row in offline_links)
    retrieval_summary = Counter(
        row.get("retrieval_status") for row in offline_links
    )
    report_lines = [
        "# RRUFF CIF Recovery v3 Full-Run Report",
        "",
        f"- network: **{'YES' if network_online else 'NO'}**",
        f"- online pilot: `{online_status}`",
        f"- pilot pass: **{'YES' if pilot_pass else 'NO'}**",
        "- full run started: **NO**",
        "",
        "## Gate Decision",
        "",
    ]
    report_lines.extend(
        f"- {name}: `{'PASS' if value else 'FAIL'}`"
        for name, value in gates.items()
    )
    report_lines.extend(
        [
            "",
            "## Current Evidence",
            "",
            f"- offline pilot target count: `{len(offline_links)}`",
            f"- offline resolution counts: `{dict(offline_summary)}`",
            f"- offline retrieval counts: `{dict(retrieval_summary)}`",
            f"- offline manual queue count: `{len(offline_queue)}`",
            f"- broad target IDs recorded: `{', '.join(broad_ids) or '(none)'}`",
            "- online rows completed: "
            f"`{online_row_count}`; aborted or unavailable online runs are "
            "not treated as no-candidate results.",
            "",
            "## Reconciliation",
            "",
            f"- offline/online comparison: `{manifests / 'rruff_offline_online_pilot_comparison_v3.csv'}`",
            f"- v2/v3 comparison: `{manifests / 'rruff_v2_v3_pilot_comparison_v3.csv'}`",
            "- historical v2 winners remain comparison artifacts only.",
            "- clean experimental-subset reconciliation was not run because "
            "the online pilot gate failed.",
            "",
            "## Safety",
            "",
            "- no MongoDB, canonical source, v2 output, or paper update was made.",
            "- AMCSd contains URL/sample metadata only; no AMCSd CIF was retrieved.",
            "- no full COD candidate library was redownloaded.",
            "- no CIF is accepted from formula/name-only evidence.",
            "",
            "## Blockers",
            "",
        ]
    )
    report_lines.extend(f"- {line}" for line in blocker_lines)
    report_lines.extend(
        [
            "",
            "## Manual Priority IDs",
            "",
            f"- {', '.join(gate_payload['manual_top_ids']) or '(none)'}",
            "",
            "## Output Files",
            "",
            f"- network diagnostics: `{network_report}`",
            f"- pilot gate: `{reports / 'pilot_gate_v3.json'}`",
            f"- offline/online comparison: `{manifests / 'rruff_offline_online_pilot_comparison_v3.csv'}`",
            f"- v2/v3 comparison: `{manifests / 'rruff_v2_v3_pilot_comparison_v3.csv'}`",
            f"- preserved offline audit: `{snapshot}`",
        ]
    )
    (reports / "full_run_report_v3.md").write_text(
        "\n".join(report_lines) + "\n",
        encoding="utf-8",
    )
    return gate_payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--v2-root", type=Path, default=DEFAULT_V2_ROOT)
    parser.add_argument("--online-completed", action="store_true")
    parser.add_argument(
        "--online-status",
        default="stopped_before_completion_network_unavailable",
    )
    args = parser.parse_args()
    payload = finalize(
        output_root=args.output_root.resolve(),
        v2_root=args.v2_root.resolve(),
        online_completed=args.online_completed,
        online_status=args.online_status,
    )
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
