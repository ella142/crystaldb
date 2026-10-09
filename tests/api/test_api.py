from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from crystaldb.api.config import get_settings
from crystaldb.api.db import get_client
from crystaldb.api.main import app
from crystaldb.api.services.files import resolve_registered_file
from crystaldb.api.services.mapping import (
    measurement_model,
    pattern_model,
    structure_model,
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    # API tests may insert temporary documents; never point them at production.
    os.environ["CRYSTALDB_MONGO_DB"] = "crystaldb_api_pilot"
    get_settings.cache_clear()
    get_client.cache_clear()
    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_stats_include_database_source_and_phase_breakdowns(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/stats")
    assert response.status_code == 200
    stats = response.json()
    database = get_client()[get_settings().mongo_db]

    source_counts = {
        row["_id"]: row["count"]
        for row in database.patterns.aggregate(
            [
                {"$match": {"modality": "powder_xrd"}},
                {"$group": {"_id": "$api_source_code", "count": {"$sum": 1}}},
            ]
        )
        if row.get("_id")
    }
    phase_counts = {
        row["_id"]: row["count"]
        for row in database.patterns.aggregate(
            [
                {
                    "$group": {
                        "_id": {"$ifNull": ["$phase_character", "unknown"]},
                        "count": {"$sum": 1},
                    }
                }
            ]
        )
    }

    assert stats["powder_pattern_counts_by_source"] == source_counts
    assert stats["phase_character_counts"] == phase_counts
    assert sum(source_counts.values()) == stats["powder_pattern_count"]
    assert sum(phase_counts.values()) == stats["pattern_count"]
    expected_source_phase_counts: dict[str, dict[str, int]] = {}
    for row in database.patterns.aggregate(
        [
            {
                "$group": {
                    "_id": {
                        "source": "$api_source_code",
                        "phase": {"$ifNull": ["$phase_character", "unknown"]},
                    },
                    "count": {"$sum": 1},
                }
            }
        ]
    ):
        source = row["_id"].get("source")
        phase = row["_id"].get("phase")
        if source and phase:
            expected_source_phase_counts.setdefault(source, {})[phase] = row["count"]
    assert stats["source_phase_counts"] == expected_source_phase_counts


def test_pattern_list(client: TestClient) -> None:
    response = client.get("/api/v1/patterns?limit=50")
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["count"] == 16
    assert payload["meta"]["total_count"] == 16
    assert len(payload["items"]) == 16
    assert all("pattern_id" in item for item in payload["items"])
    assert "data" not in payload["items"][0]


def test_reflection_sets_are_listed_with_total_count_and_source_filter(
    client: TestClient,
) -> None:
    database = get_client()[get_settings().mongo_db]
    response = client.get("/api/v1/reflection-sets?source=COD&limit=2")
    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["total_count"] == database.reflection_sets.count_documents(
        {"api_source_code": "COD"}
    )
    assert payload["items"]
    assert all(
        item["modality"] == "single_crystal_xrd" for item in payload["items"]
    )
    assert all(item["source"]["code"] == "COD" for item in payload["items"])
    assert all("available_fields" in item for item in payload["items"])

    source_id = payload["items"][0]["source"]["source_id"]
    query_response = client.get(
        f"/api/v1/reflection-sets?q={source_id}&limit=5"
    )
    assert query_response.status_code == 200
    assert query_response.json()["items"]


def test_global_search_covers_rruff_record_identifiers(client: TestClient) -> None:
    response = client.get("/api/v1/search?q=R080016")
    assert response.status_code == 200
    payload = response.json()
    assert "reflection_sets" in payload
    assert [item["pattern_id"] for item in payload["patterns"]] == [
        "RRUFF_PAT_R080016_1"
    ]
    assert "RRUFF_SAM_R080016" in [
        item["sample_id"] for item in payload["samples"]
    ]


def test_pattern_detail(client: TestClient) -> None:
    response = client.get("/api/v1/patterns/RRUFF_PAT_R040043_1")
    assert response.status_code == 200
    payload = response.json()
    assert payload["phase_character"] == "multi_phase"
    assert payload["structure_linkage"]["status"] == "unlinked"


def test_invalid_pattern_is_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/patterns/DOES_NOT_EXIST")
    assert response.status_code == 404


def test_pattern_filters(client: TestClient) -> None:
    response = client.get("/api/v1/patterns?source=DARA")
    assert response.status_code == 200
    assert response.json()["meta"]["count"] == 12
    assert response.json()["meta"]["total_count"] == 12
    response = client.get("/api/v1/patterns?phase_character=multi_phase")
    assert response.status_code == 200
    assert response.json()["meta"]["count"] == 3
    assert response.json()["meta"]["total_count"] == 3
    legacy_role = client.get(
        "/api/v1/patterns?source=DARA&dataset_role=single_precursor"
    )
    assert legacy_role.status_code == 422
    assert (
        client.get(
            "/api/v1/patterns?source=DARA&dataset_role=single_phase_precursor"
        ).json()["meta"]["count"]
        == 10
    )


def test_component_formula_filter_accepts_underscore_notation(client: TestClient) -> None:
    underscore_response = client.get("/api/v1/patterns?component_formula=Ag_2_S")
    plain_response = client.get("/api/v1/patterns?component_formula=Ag2S")
    assert underscore_response.status_code == 200
    assert plain_response.status_code == 200
    assert underscore_response.json()["meta"]["total_count"] > 0
    assert (
        underscore_response.json()["meta"]["total_count"]
        == plain_response.json()["meta"]["total_count"]
    )


def test_multiphase_components_are_explicit(client: TestClient) -> None:
    response = client.get("/api/v1/patterns/RRUFF_PAT_R040043_1")
    components = response.json()["phase_components"]
    assert len(components) == 2
    assert components[0]["fraction"]["basis"] in {"weight_fraction", "percent_unspecified"}
    assert all(component["structure"]["structure_id"] is None for component in components)


def test_dara_mixture_scans_share_sample_but_not_measurement_or_pattern(
    client: TestClient,
) -> None:
    items = client.get(
        "/api/v1/patterns?source=DARA&dataset_role=precursor_mixture_benchmark"
    ).json()["items"]
    assert len(items) == 2
    by_pattern = {item["pattern_id"].rsplit("_", 1)[-1]: item for item in items}
    two_min = by_pattern["2min"]
    eight_min = by_pattern["8min"]
    assert two_min["sample_id"] == eight_min["sample_id"]
    assert two_min["measurement_id"] != eight_min["measurement_id"]
    assert two_min["pattern_id"] != eight_min["pattern_id"]


def test_dara_component_formulas_fractions_and_provenance(client: TestClient) -> None:
    pattern_id = (
        "DARA_PAT_In2O3_0p3022_La_OH_3_0p5014_TiO2_0p2004_2min"
    )
    payload = client.get(f"/api/v1/patterns/{pattern_id}").json()
    assert [item["formula"] for item in payload["phase_components"]] == [
        "In2O3",
        "La(OH)3",
        "TiO2",
    ]
    assert [item["fraction"]["value"] for item in payload["phase_components"]] == pytest.approx(
        [0.3022, 0.5014, 0.2004]
    )
    assert all(
        item["fraction"]["basis"] == "weight_fraction"
        for item in payload["phase_components"]
    )
    assert payload["provenance"]["label_type"] == "source_ground_truth"
    assert payload["provenance"]["label_method"] == "known_precursor_mixture"


def test_dara_single_precursor_comes_from_canonical_data(client: TestClient) -> None:
    response = client.get("/api/v1/patterns/DARA_PAT_TiO2_SINGLE_PRECURSOR")
    assert response.status_code == 200
    payload = response.json()
    assert payload["phase_character"] == "single_phase"
    assert payload["dataset_role"] == "single_phase_precursor"
    assert payload["phase_components"][0]["formula"] == "TiO2"
    assert payload["provenance"]["label_type"] == "source_ground_truth"
    assert payload["provenance"]["label_method"] == "known_single_precursor"
    assert payload["radiation"]["wavelength_angstrom"] == pytest.approx(1.540598)
    measurement = client.get(
        "/api/v1/measurements/DARA_MEAS_TiO2_SINGLE_PRECURSOR"
    ).json()
    assert measurement["conditions"]["anode"] == "Cu"
    assert measurement["conditions"]["step_size"] == pytest.approx(0.01086644)


def test_unknown_rruff_phase_character_and_wavelength_remain_unknown(
    client: TestClient,
) -> None:
    payload = client.get("/api/v1/patterns/RRUFF_PAT_R080016_1").json()
    assert payload["phase_character"] == "unknown"
    assert payload["radiation"]["wavelength_angstrom"] is None
    measurement = client.get("/api/v1/measurements/RRUFF_MEAS_R080016_1").json()
    assert measurement["conditions"]["radiation"] is None
    assert measurement["conditions"]["wavelength_angstrom"] is None


def test_dara_canonical_measurement_conditions_survive_mapping(client: TestClient) -> None:
    measurement_id = (
        "DARA_MEAS_In2O3_0p3022_La_OH_3_0p5014_TiO2_0p2004_2min"
    )
    payload = client.get(f"/api/v1/measurements/{measurement_id}").json()
    assert payload["conditions"]["radiation"] == "K-Alpha 1"
    assert payload["conditions"]["wavelength_angstrom"] == pytest.approx(1.540598)
    assert payload["conditions"]["anode"] == "Cu"
    assert payload["conditions"]["scan_range"] == pytest.approx(
        [10.02173288, 99.99585608]
    )
    assert payload["conditions"]["counting_time_seconds"] == pytest.approx(10.965)
    assert payload["conditions"]["scan_program"] == "Continuous"
    assert payload["conditions"]["step_size"] == pytest.approx(0.04346576)
    assert payload["sample_id"] == (
        "DARA_SAM_In2O3_0p3022_La_OH_3_0p5014_TiO2_0p2004"
    )
    pattern = client.get(
        "/api/v1/patterns/DARA_PAT_In2O3_0p3022_La_OH_3_0p5014_TiO2_0p2004_2min"
    ).json()
    assert pattern["scan"]["axis"] == "two_theta"


def test_measurement_mapper_prefers_canonical_condition_keys() -> None:
    result = measurement_model(
        {
            "measurement_id": "TEST_MEAS",
            "api_source_code": "TEST",
            "conditions": {
                "radiation": "source canonical radiation",
                "wavelength_angstrom": "1.2345",
                "scan_range": [12, 48],
                "counting_time_seconds": "7.5",
                "scan_program": "canonical program",
            },
            "radiation": {
                "characteristic": "legacy radiation",
                "wavelength_kalpha1_angstrom": 9.876,
            },
            "counting_time_seconds": 99,
            "scan_program": "legacy program",
        }
    )
    assert result.conditions.radiation == "source canonical radiation"
    assert result.conditions.wavelength_angstrom == pytest.approx(1.2345)
    assert result.conditions.scan_range == [12, 48]
    assert result.conditions.counting_time_seconds == pytest.approx(7.5)
    assert result.conditions.scan_program == "canonical program"


def test_structure_id_filter_finds_registered_pattern_link(client: TestClient) -> None:
    response = client.get("/api/v1/patterns?structure_id=STR_COD_9000253")
    assert response.status_code == 200
    assert [item["pattern_id"] for item in response.json()["items"]] == [
        "RRUFF_PAT_R080016_1"
    ]


def test_ambiguous_structure_linkage_preserves_candidates() -> None:
    pattern = pattern_model(
        {
            "pattern_id": "TEST_PAT_AMBIGUOUS",
            "api_source_code": "TEST",
            "structure_linkage": {
                "status": "ambiguous",
                "coverage": "partial",
                "certainty": "ambiguous",
                "candidate_structure_ids": ["STR_A", "STR_B"],
            },
            "phase_components": [
                {
                    "formula": "AB",
                    "structure": {
                        "status": "ambiguous",
                        "structure_ids": ["STR_A", "STR_B"],
                        "coverage": "partial",
                        "certainty": "ambiguous",
                    },
                }
            ],
        }
    )
    assert pattern.structure_linkage.status == "ambiguous"
    assert pattern.structure_linkage.coverage == "partial"
    assert pattern.structure_linkage.certainty == "ambiguous"
    assert pattern.structure_linkage.candidate_structure_ids == ["STR_A", "STR_B"]
    phase_structure = pattern.phase_components[0].structure
    assert phase_structure.structure_id is None
    assert phase_structure.structure_ids == ["STR_A", "STR_B"]


def test_relation_backed_pattern_linkage_is_authoritative() -> None:
    pattern = pattern_model(
        {
            "pattern_id": "POWBASE_PAT_113",
            "api_source_code": "POWBASE",
            "structure_linkage": {
                "status": "unlinked",
                "coverage": "none",
                "certainty": "unknown",
                "candidate_structure_ids": [],
            },
        },
        relation_documents=[
            {
                "object_type": "structure",
                "object_id": "STR_POWBASE_113_PHASE_1",
                "predicate": "has_structure_linkage",
                "status": "complete",
            }
        ],
    )
    assert pattern.structure_linkage.status == "complete"
    assert pattern.structure_linkage.candidate_structure_ids == [
        "STR_POWBASE_113_PHASE_1"
    ]


def test_powbase_structure_without_relation_is_not_promoted() -> None:
    pattern = pattern_model(
        {
            "pattern_id": "POWBASE_PAT_106",
            "api_source_code": "POWBASE",
            "linked_structure_ids": ["STR_POWBASE_106_PHASE_1"],
            "structure_linkage": {
                "status": "complete",
                "coverage": "complete",
                "certainty": "resolved",
                "candidate_structure_ids": ["STR_POWBASE_106_PHASE_1"],
            },
        },
        relation_documents=[],
    )
    assert pattern.structure_linkage.status == "unlinked"
    assert pattern.structure_linkage.candidate_structure_ids == []


def test_powbase_label_and_multiple_wavelengths_are_preserved() -> None:
    pattern = pattern_model(
        {
            "pattern_id": "POWBASE_PAT_113",
            "api_source_code": "POWBASE",
            "provenance": {
                "powbase_source_evidence": {
                    "source_label_raw": "amphibole",
                }
            },
            "radiation": {
                "wavelength_angstrom": 1.54056,
                "wavelength_kalpha2_angstrom": 1.54439,
            },
        }
    )
    assert pattern.material_label == "amphibole"
    assert pattern.radiation.wavelengths_angstrom == pytest.approx(
        [1.54056, 1.54439]
    )


def test_xy_point_count_consistency(client: TestClient) -> None:
    response = client.get("/api/v1/patterns/RRUFF_PAT_R040043_1/xy")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["x"]["values"]) == len(payload["y"]["values"])
    detail = client.get("/api/v1/patterns/RRUFF_PAT_R040043_1").json()
    assert len(payload["x"]["values"]) == detail["scan"]["point_count"]


def test_structure_detail(client: TestClient) -> None:
    response = client.get("/api/v1/structures/STR_COD_1100908")
    assert response.status_code == 200
    assert response.json()["source"]["code"] == "COD"
    assert response.json()["formula"] == "C18 H22 Cu N2 O5"
    assert response.json()["atom_site_count"] == 25


def test_cif_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/structures/STR_COD_1100908/cif")
    assert response.status_code == 200
    assert b"data_1100908" in response.content


def test_reflection_id_uses_public_prefix(client: TestClient) -> None:
    response = client.get("/api/v1/reflection-sets/REFL_COD_1100908")
    assert response.status_code == 200
    assert response.json()["reflection_set_id"] == "REFL_COD_1100908"


def test_structure_and_relation_provenance_are_separate(client: TestClient) -> None:
    structure = client.get("/api/v1/structures/STR_COD_9000253")
    assert structure.status_code == 200
    provenance = structure.json()["provenance"]
    assert provenance["source"] == "COD"
    assert provenance["source_id"] == "9000253"
    assert provenance["label_method"] == "COD_CIF"
    assert "rruff" not in str(provenance).casefold()

    database = get_client()[get_settings().mongo_db]
    relation = database.relations.find_one(
        {
            "subject_id": "RRUFF_PAT_R080016_1",
            "object_id": "STR_COD_9000253",
        },
        {"_id": 0},
    )
    assert relation is not None
    assert relation["provenance"]["method"] == "existing_rruff_structure_link"


def test_atom_site_count_semantics_are_explicit(client: TestClient) -> None:
    payload = client.get("/api/v1/structures/STR_COD_9000253").json()
    assert payload["atom_site_count"] == 3
    assert "atom_count" not in payload
    mapped = structure_model(
        {
            "structure_id": "TEST_STRUCTURE",
            "api_source_code": "COD",
            "atom_count": 2,
            "atomic_sites": [{"label": "A"}, {"label": "B"}],
        }
    )
    assert mapped.atom_site_count == 2
    assert "atom_count" not in mapped.model_dump()


def test_missing_cif_is_not_found(client: TestClient) -> None:
    settings = get_settings()
    database = get_client()[settings.mongo_db]
    database.structures.insert_one(
        {
            "structure_id": "TEST_STR_MISSING_CIF",
            "api_source_code": "TEST",
            "api_source_id": "missing",
            "source": {"code": "TEST", "source_id": "missing"},
            "file": {"key": "does-not-exist.cif"},
        }
    )
    try:
        response = client.get("/api/v1/structures/TEST_STR_MISSING_CIF/cif")
        assert response.status_code == 404
    finally:
        database.structures.delete_one({"structure_id": "TEST_STR_MISSING_CIF"})


def test_path_traversal_is_rejected(client: TestClient) -> None:
    with pytest.raises(ValueError):
        resolve_registered_file("../outside.cif", get_settings().data_root)

    database = get_client()[get_settings().mongo_db]
    database.structures.insert_one(
        {
            "structure_id": "TEST_STR_TRAVERSAL",
            "api_source_code": "TEST",
            "api_source_id": "traversal",
            "source": {"code": "TEST", "source_id": "traversal"},
            "file": {"key": "../outside.cif"},
        }
    )
    try:
        response = client.get("/api/v1/structures/TEST_STR_TRAVERSAL/cif")
        assert response.status_code == 400
    finally:
        database.structures.delete_one({"structure_id": "TEST_STR_TRAVERSAL"})

    with pytest.raises(ValueError):
        resolve_registered_file("../outside.hkl", get_settings().data_root)

    database.reflection_sets.insert_one(
        {
            "reflection_set_id": "TEST_REFL_TRAVERSAL",
            "api_source_code": "TEST",
            "api_source_id": "traversal",
            "source": {"code": "TEST", "source_id": "traversal"},
            "file": {"key": "../outside.hkl"},
        }
    )
    try:
        response = client.get("/api/v1/reflection-sets/TEST_REFL_TRAVERSAL/hkl")
        assert response.status_code == 400
    finally:
        database.reflection_sets.delete_one(
            {"reflection_set_id": "TEST_REFL_TRAVERSAL"}
        )
