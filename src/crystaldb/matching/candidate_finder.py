from crystaldb.matching.candidate_compare import (
    compare_candidate,
)


def find_candidates(
    signature,
    cif_index,
    max_length_difference=0.05,
    max_angle_difference=2.0,
):
    """
    Find plausible CIF candidates for one RRUFF signature.

    This stage is intentionally broader than the final
    matching rules. Its purpose is candidate recall,
    not automatic confirmation.
    """

    results = []

    for cif_record in cif_index:

        # Skip CIF records that failed to parse.
        if cif_record.get("parse_status") != "ok":
            continue

        # --------------------------------
        # Compare general structure info
        # --------------------------------
        comparison = compare_candidate(
            signature,
            cif_record,
        )

        # --------------------------------
        chemistry = comparison.get(
            "chemistry",
            {}
        )

        chemistry_compatible = chemistry.get(
            "compatible"
        )

        # --------------------------------
        # Name evidence
        # --------------------------------
        sample_name_match = comparison.get(
            "sample_name_match",
            False,
        )

        reference_name_match = comparison.get(
            "reference_name_match",
            False,
        )

        name_support = (
            sample_name_match
            or reference_name_match
        )

        # --------------------------------
        # Space-group evidence
        # --------------------------------
        sg_equivalent = (
            comparison
            .get("space_group", {})
            .get("equivalent")
        )

        # --------------------------------
        # Unit-cell evidence
        # --------------------------------
        cell = comparison.get(
            "cell",
            {},
        )

        length_diff = cell.get(
            "max_length_relative_difference"
        )

        angle_diff = cell.get(
            "max_angle_difference"
        )

        broad_cell_match = (
            length_diff is not None
            and angle_diff is not None
            and length_diff
            <= max_length_difference
            and angle_diff
            <= max_angle_difference
        )

        # --------------------------------
        # Candidate role classification
        # --------------------------------

        candidate_type = None


        # ========================================
        # 1. Sample -> CIF candidate
        # ========================================

        # Chemistry explicitly supports the
        # sample-to-CIF relationship.
        if (
            chemistry_compatible is True
            and sg_equivalent is True
            and broad_cell_match
        ):
            candidate_type = "sample_candidate"


        # Chemistry cannot yet be interpreted safely,
        # so require the SAMPLE mineral name itself
        # to support the relationship.
        elif (
            chemistry_compatible is None
            and sample_name_match
            and sg_equivalent is True
            and broad_cell_match
        ):
            candidate_type = (
                "sample_candidate_chemistry_unknown"
            )


        # ========================================
        # 2. RRUFF DIF reference structure -> CIF
        # ========================================

        elif (
            reference_name_match
            and sg_equivalent is True
            and broad_cell_match
        ):
            candidate_type = (
                "reference_structure_candidate"
            )


        # ========================================
        # 3. Symmetry-conflict review candidate
        # ========================================

        # Keep a structure for review when:
        # - chemistry does not explicitly conflict
        # - the mineral/reference name supports it
        # - the unit cell is close
        # - but the space groups are NOT equivalent
        #
        # Example:
        # R250095 Abellaite:
        # P63mc vs COD 9017418 P31c
        elif (
            chemistry_compatible is not False
            and (
                sample_name_match
                or reference_name_match
            )
            and broad_cell_match
            and sg_equivalent is False
        ):
            candidate_type = (
                "symmetry_conflict_candidate"
            )


        else:
            continue

        # --------------------------------
        # Store candidate
        # --------------------------------
        results.append(
            {
                "source":
                    cif_record.get("source"),

                "candidate_type":
                    candidate_type,

                "chemistry":
                    chemistry,

                "source_id":
                    cif_record.get("source_id"),

                "file_path":
                    cif_record.get("file_path"),

                "mineral_name":
                    cif_record.get(
                        "mineral_name"
                    ),

                "evidence": {
                    "sample_name_match":
                        sample_name_match,

                    "chemistry_compatible":
                        chemistry_compatible,

                    "reference_name_match":
                        reference_name_match,

                    "name_support":
                        name_support,

                    "space_group_equivalent":
                        sg_equivalent,

                    "broad_cell_match":
                        broad_cell_match,

                    "max_length_relative_difference":
                        length_diff,

                    "max_angle_difference":
                        angle_diff,
                },
            }
        )

    # --------------------------------
    # Sort candidates
    #
    # Priority:
    # 1. More positive evidence
    # 2. Smaller cell-length difference
    # 3. Smaller cell-angle difference
    # --------------------------------
    results.sort(
        key=lambda item: (
            (
                item["evidence"][
                    "max_length_relative_difference"
                ]
                if item["evidence"][
                    "max_length_relative_difference"
                ]
                is not None
                else float("inf")
            ),

            (
                item["evidence"][
                    "max_angle_difference"
                ]
                if item["evidence"][
                    "max_angle_difference"
                ]
                is not None
                else float("inf")
            ),
        )
    ) 

    return results