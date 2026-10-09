from __future__ import annotations

import zipfile
import hashlib
from pathlib import Path

from scripts.audit_powbase import (
    inspect_archive,
    parse_index_bytes,
    parse_index_record,
)


INDEX_URL = (
    "https://www.cristal.org/DU-SDPD/nexus/albweb/univ-lem/powbase/powbase.txt"
)


def write_single_member_zip(
    path: Path,
    filename: str,
    content: bytes,
) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(filename, content)


def get_dat_member(record: dict) -> dict:
    return next(
        member
        for member in record["members"]
        if member["member_filename"].casefold().endswith(".dat")
    )


def test_parse_index_preserves_raw_line_and_hash_tokens() -> None:
    raw_line = (
        b'<a href="17.zip">TiO2</a>#Cu-Kalpha#synchrotron#'
        b"Author et al., Journal 12 (1999)#comment\r\n"
    )

    records, summary = parse_index_bytes(raw_line, INDEX_URL)

    assert summary["index_entry_count"] == 1
    record = records[0]
    assert record["entry_id"] == "17"
    assert record["zip_url"].endswith("/powbase/17.zip")
    assert record["raw_index_text"] == raw_line.decode("latin-1")
    assert record["raw_line_ending"] == "\r\n"
    assert record["raw_hash_delimited_tokens"] == [
        "Cu-Kalpha",
        "synchrotron",
        "Author et al., Journal 12 (1999)",
        "comment",
    ]
    assert record["raw_bibliographic_comment_text"].startswith("#")
    assert record["apparent_formula_name_token"] == "TiO2"


def test_parse_index_keeps_unknown_token_unknown() -> None:
    raw_line = (
        b'<a href="/DU-SDPD/nexus/albweb/univ-lem/powbase/18.zip">'
        b"18.zip</a>#unknown#1.52904#not enough context\n"
    )

    records, _ = parse_index_bytes(raw_line, INDEX_URL)

    assert records[0]["entry_id"] == "18"
    assert records[0]["apparent_formula_name_token"] is None
    assert records[0]["raw_hash_delimited_tokens"][0] == "unknown"
    assert "1.52904" in records[0]["raw_hash_delimited_tokens"]


def test_simple_legacy_intensity_array_is_grid_validated(tmp_path: Path) -> None:
    zip_path = tmp_path / "1.zip"
    data = (
        b"! sample\n"
        b"0.0 1.0 2.0\n"
        b"10 20\n"
        b"30 0\n"
    )
    write_single_member_zip(zip_path, "1.dat", data)

    record = inspect_archive(
        zip_path,
        {
            "entry_id": "1",
            "zip_url": f"{INDEX_URL.rsplit('/', 1)[0]}/1.zip",
            "apparent_formula_name_token": "Example",
        },
    )
    member = get_dat_member(record)

    assert member["detected_content_family"] == "legacy_intensity_array"
    assert member["diffraction_array"] is True
    assert member["expected_point_count"] == 3
    assert member["raw_numeric_value_count"] == 4
    assert member["observed_intensity_count"] == 4
    assert (
        member["observed_intensity_count_excluding_trailing_zero_padding"]
        == 3
    )
    assert member["trailing_zero_padding_count"] == 1
    assert member["trailing_zero_padding_candidate"] is True
    assert member["fixed_width_padding_candidate"] is True
    assert member["point_count_consistency"] is True


def test_count_mismatch_remains_unknown(tmp_path: Path) -> None:
    zip_path = tmp_path / "2.zip"
    data = b"0.0 1.0 2.0\n10 20 30 40\n"
    write_single_member_zip(zip_path, "2.dat", data)

    record = inspect_archive(
        zip_path,
        {
            "entry_id": "2",
            "zip_url": f"{INDEX_URL.rsplit('/', 1)[0]}/2.zip",
            "apparent_formula_name_token": "Example",
        },
    )
    member = get_dat_member(record)

    assert member["detected_content_family"] == "legacy_intensity_array"
    assert member["diffraction_array"] is None
    assert member["expected_point_count"] == 3
    assert member["observed_intensity_count"] == 4
    assert member["point_count_consistency"] is False
    assert member["point_count_review_reasons"]


def test_commented_pdcif_metadata_and_phases_are_recovered(tmp_path: Path) -> None:
    zip_path = tmp_path / "89.zip"
    data = (
        b"!data_example_phase_1\n"
        b"!_pd_phase_block_id PHASE_1\n"
        b"!_pd_phase_name Alpha\n"
        b"!_pd_instr_radiation_probe x-ray\n"
        b"!_diffrn_radiation_wavelength 1.15023\n"
        b"!_pd_meas_2theta_range_min 0.0\n"
        b"!_pd_meas_2theta_range_max 2.0\n"
        b"!_pd_meas_2theta_range_inc 1.0\n"
        b"!loop_\n"
        b"!_pd_meas_intensity_total\n"
        b"0.0 1.0 2.0\n"
        b"10 20\n"
        b"30 0\n"
    )
    write_single_member_zip(zip_path, "89.dat", data)

    record = inspect_archive(
        zip_path,
        {
            "entry_id": "89",
            "zip_url": f"{INDEX_URL.rsplit('/', 1)[0]}/89.zip",
            "apparent_formula_name_token": "Example",
        },
    )
    member = get_dat_member(record)

    assert member["detected_content_family"] == "commented_pdcif"
    assert member["diffraction_array"] is True
    assert member["source_radiation_probe"] == ["x-ray"]
    assert member["source_wavelength"] == ["1.15023"]
    assert member["explicit_phase_block_count"] == 1
    assert member["source_phase_names"] == ["Alpha"]
    assert "_pd_meas_intensity_total" in member["source_intensity_loop_tags"]


def test_fullprof_style_pattern_and_wavelength_are_recovered(
    tmp_path: Path,
) -> None:
    zip_path = tmp_path / "169.zip"
    data = (
        b"#COMM   In2O3   D8-Advance\n"
        b"#! lambda1 Lambda2 Ratio\n"
        b"# 1.540560 1.544390 -0.4800\n"
        b"#! Data for PHASE number: 1\n"
        b"#In2O3\n"
        b"0.0 1.0 2.0\n"
        b"10 20\n"
        b"30 0\n"
    )
    write_single_member_zip(zip_path, "169.dat", data)

    record = inspect_archive(
        zip_path,
        {
            "entry_id": "169",
            "zip_url": f"{INDEX_URL.rsplit('/', 1)[0]}/169.zip",
            "apparent_formula_name_token": "In2O3",
        },
    )
    member = get_dat_member(record)

    assert member["detected_content_family"] == "fullprof_style_pattern"
    assert member["diffraction_array"] is True
    assert member["source_wavelength"] == ["1.540560", "1.544390"]
    assert member["explicit_phase_block_count"] == 1
    assert member["source_phase_names"] == ["In2O3"]
    assert member["metadata_conflict"] is False


def test_fullprof_metadata_conflict_is_reported(tmp_path: Path) -> None:
    zip_path = tmp_path / "169b.zip"
    data = (
        b"#COMM   In2O3   D8-Advance\n"
        b"#! Data for PHASE number: 1\n"
        b"#CeO2\n"
        b"0.0 1.0 2.0\n"
        b"10 20\n"
        b"30 0\n"
    )
    write_single_member_zip(zip_path, "169b.dat", data)

    record = inspect_archive(
        zip_path,
        {
            "entry_id": "169b",
            "zip_url": f"{INDEX_URL.rsplit('/', 1)[0]}/169b.zip",
            "apparent_formula_name_token": "In2O3",
        },
    )
    member = get_dat_member(record)

    assert member["metadata_conflict"] is True
    assert any("CeO2" in note for note in member["metadata_conflict_notes"])


def test_zip_inventory_inspects_members_without_ingestion(tmp_path: Path) -> None:
    zip_path = tmp_path / "17.zip"
    data = b"0.0 1.0 2.0\n10 20\n30 0\n"
    cif = b"_chemical_name_common 'example'\n"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("17.dat", data)
        archive.writestr("metadata.cif", cif)
        archive.writestr("image.gif", b"GIF89a")

    entry = {
        "entry_id": "17",
        "zip_url": f"{INDEX_URL.rsplit('/', 1)[0]}/17.zip",
        "apparent_formula_name_token": "Example",
    }
    record = inspect_archive(zip_path, entry)

    assert record["archive_open_status"] == "ok"
    assert record["contained_filenames"] == ["17.dat", "metadata.cif", "image.gif"]
    assert record["dat_files"] == ["17.dat"]
    assert record["cif_files"] == ["metadata.cif"]
    assert record["other_files"] == ["image.gif"]
    dat_member = get_dat_member(record)
    assert dat_member["numeric_array_present"] is True
    assert dat_member["diffraction_arrays_present"] is True


def test_non_zip_text_payload_137_is_audited_without_rewrite(
    tmp_path: Path,
) -> None:
    path = tmp_path / "137.zip"
    intensities = [
        str((index % 17) + 1)
        for index in range(3001)
    ] + ["0"] * 9
    rows = [
        "! KCAF3 SOLUTION 1 ANISO",
        "15.00 0.04 135.00",
    ]
    rows.extend(
        " ".join(intensities[index : index + 10])
        for index in range(0, len(intensities), 10)
    )
    original = ("\r\n".join(rows) + "\r\n").encode("ascii")
    path.write_bytes(original)
    original_sha256 = hashlib.sha256(original).hexdigest()

    record = inspect_archive(
        path,
        {
            "entry_id": "137",
            "zip_url": f"{INDEX_URL.rsplit('/', 1)[0]}/137.zip",
            "apparent_formula_name_token": "KCaF3",
        },
    )
    payload = record["payload_record"]

    assert path.read_bytes() == original
    assert record["source_filename"] == "137.zip"
    assert record["original_filename"] == "137.zip"
    assert record["source_sha256"] == original_sha256
    assert record["original_sha256"] == original_sha256
    assert record["zip_sha256"] == original_sha256
    assert record["archive_open_status"] == "not_zip_readable_text"
    assert record["archive_container_type"] == "plain_text"
    assert record["archive_content_status"] == (
        "readable_text_supported_diffraction"
    )
    assert record["archive_usable_for_audit"] is True
    assert record["contained_filenames"] == []
    assert record["payload_filename"] == "137.zip"
    assert payload["source_extension"] == ".zip"
    assert payload["detected_content_family"] == "legacy_intensity_array"
    assert payload["diffraction_array"] is True
    assert payload["two_theta_start_raw"] == "15.00"
    assert payload["step_raw"] == "0.04"
    assert payload["two_theta_end_raw"] == "135.00"
    assert payload["expected_point_count"] == 3001
    assert payload["raw_numeric_value_count"] == 3010
    assert payload["observed_intensity_count"] == 3010
    assert (
        payload["observed_intensity_count_excluding_trailing_zero_padding"]
        == 3001
    )
    assert payload["trailing_zero_padding_count"] == 9
    assert payload["trailing_zero_padding_candidate"] is True
    assert payload["fixed_width_padding_candidate"] is True
    assert payload["point_count_consistency"] is True
    assert payload["experimental_profile_parse_status"] == (
        "candidate_safe_after_terminal_padding_review"
    )


def test_parse_index_record_returns_none_without_zip() -> None:
    assert (
        parse_index_record(
            line_number=1,
            raw_bytes=b"#comment\n",
            raw_line="#comment",
            raw_eol="\n",
            index_url=INDEX_URL,
        )
        is None
    )
