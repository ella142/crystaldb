def classify_candidate(
    comparison,
    strong_max_length_difference=0.005,
    strong_max_angle_difference=0.5,
    candidate_max_length_difference=0.02,
    candidate_max_angle_difference=1.0,
):
    """
    crystaldb v0.3 matching rules.

    Distinguishes two relationships:

    1. sample_structure
       CIF is a candidate structure for the measured
       RRUFF mineral/sample.

    2. reference_structure
       CIF corresponds to the reference structure
       used by the RRUFF DIF record.

    Chemistry refers to the RRUFF sample chemistry,
    so it is used primarily for sample_structure
    matching.
    """

    sample_name_match = comparison.get(
        "sample_name_match",
        False,
    )

    reference_name_match = comparison.get(
        "reference_name_match",
        False,
    )

    chemistry_compatible = (
        comparison
        .get("chemistry", {})
        .get("compatible")
    )

    sg_equivalent = (
        comparison
        .get("space_group", {})
        .get("equivalent")
    )

    cell = comparison.get("cell", {})

    length_diff = cell.get(
        "max_length_relative_difference"
    )

    angle_diff = cell.get(
        "max_angle_difference"
    )

    strong_cell_close = (
        length_diff is not None
        and angle_diff is not None
        and length_diff
        <= strong_max_length_difference
        and angle_diff
        <= strong_max_angle_difference
    )

    candidate_cell_close = (
        length_diff is not None
        and angle_diff is not None
        and length_diff
        <= candidate_max_length_difference
        and angle_diff
        <= candidate_max_angle_difference
    )

    status = "needs_review"
    relation_type = None

    # ========================================
    # 1. Sample structure matching
    # ========================================

    # Chemistry explicitly supports the sample
    # and crystallography is very close.
    if (
        chemistry_compatible is True
        and sg_equivalent is True
        and strong_cell_close
    ):
        status = "strong_match"
        relation_type = "sample_structure"

    # Chemistry supports the sample but the
    # unit cell falls only in the broader window.
    elif (
        chemistry_compatible is True
        and sg_equivalent is True
        and candidate_cell_close
    ):
        status = "candidate"
        relation_type = "sample_structure"

    # Complex chemistry cannot yet be interpreted,
    # but the sample mineral name itself supports
    # the CIF identity.
    elif (
        chemistry_compatible is None
        and sample_name_match
        and sg_equivalent is True
        and candidate_cell_close
    ):
        status = "candidate"
        relation_type = "sample_structure"

    # ========================================
    # 2. RRUFF DIF reference structure
    # ========================================

    # This does NOT establish that the CIF is the
    # measured sample structure.
    elif (
        reference_name_match
        and sg_equivalent is True
        and candidate_cell_close
    ):
        status = "candidate"
        relation_type = "reference_structure"

    return {
        "status": status,

        "relation_type": relation_type,

        "evidence": {
            "sample_name_match":
                sample_name_match,

            "reference_name_match":
                reference_name_match,

            "chemistry_compatible":
                chemistry_compatible,

            "space_group_equivalent":
                sg_equivalent,

            "strong_cell_close":
                strong_cell_close,

            "candidate_cell_close":
                candidate_cell_close,

            "max_length_relative_difference":
                length_diff,

            "max_angle_difference":
                angle_diff,
        },

        "thresholds": {
            "strong": {
                "max_length_relative_difference":
                    strong_max_length_difference,

                "max_angle_difference":
                    strong_max_angle_difference,
            },

            "candidate": {
                "max_length_relative_difference":
                    candidate_max_length_difference,

                "max_angle_difference":
                    candidate_max_angle_difference,
            },
        },

        "rule_version": "0.3",
    }