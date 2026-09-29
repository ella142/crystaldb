from crystaldb.matching.cell_compare import (
    compare_cells,
    compare_orthorhombic_axis_permutations,
)

from crystaldb.matching.space_group import (
    compare_space_groups,
)

from crystaldb.matching.chemistry import (
    compare_chemistry,
)


def normalize_name(name):
    """
    Conservative normalization for mineral/structure names.

    Removes formatting differences such as:
    spaces, hyphens, underscores and parentheses.

    It does NOT resolve synonyms or historical names.
    """

    if name is None:
        return None

    value = str(name).strip().lower()

    return "".join(
        char
        for char in value
        if char.isalnum()
    )


def compare_candidate(
    rruff_signature,
    candidate_structure,
):
    """
    Compare one RRUFF structure signature
    with one candidate CIF structure.
    """

    # --------------------------------
    # Normalize names
    # --------------------------------

    sample_name = normalize_name(
        rruff_signature.get(
            "sample_mineral"
        )
    )

    reference_name = normalize_name(
        rruff_signature.get(
            "reference_structure_name"
        )
    )

    candidate_name = normalize_name(
        candidate_structure.get(
            "mineral_name"
        )
    )

    # --------------------------------
    # Sample mineral name comparison
    # --------------------------------

    sample_name_match = (
        sample_name is not None
        and candidate_name is not None
        and sample_name == candidate_name
    )

    # --------------------------------
    # DIF reference structure name comparison
    # --------------------------------

    reference_name_match = (
        reference_name is not None
        and candidate_name is not None
        and reference_name == candidate_name
    )

    # --------------------------------
    # Get unit cells
    # --------------------------------

    reference_cell = (
        rruff_signature.get(
            "cell_parameters"
        )
        or {}
    )

    candidate_cell = (
        candidate_structure.get(
            "cell_parameters"
        )
        or {}
    )

    # --------------------------------
    # Space-group comparison
    # --------------------------------

    space_group_comparison = (
        compare_space_groups(
            rruff_signature.get(
                "space_group"
            ),
            candidate_structure.get(
                "space_group"
            ),
        )
    )

    # --------------------------------
    # Ordinary unit-cell comparison
    # --------------------------------

    cell_comparison = compare_cells(
        reference_cell,
        candidate_cell,
    )

    cell_comparison[
        "comparison_mode"
    ] = "direct"

    cell_comparison[
        "axis_permutation_applied"
    ] = False

    cell_comparison[
        "axis_mapping"
    ] = {
        "a": "a",
        "b": "b",
        "c": "c",
    }

    # --------------------------------
    # Orthorhombic setting comparison
    # --------------------------------
    #
    # Example:
    #
    # Pbnm vs Pnma
    #
    # They may have the same space-group
    # number but use different axis settings.
    #
    # Only try axis permutations when:
    #
    # 1. Gemmi recognizes the same SG number
    # 2. current operations are not identical
    # 3. both cells are approximately orthorhombic
    #
    # The permutation helper itself checks (3).
    # --------------------------------

    if (
        space_group_comparison.get(
            "same_number"
        )
        is True
        and space_group_comparison.get(
            "equivalent"
        )
        is False
    ):
        permutation_comparison = (
            compare_orthorhombic_axis_permutations(
                reference_cell,
                candidate_cell,
            )
        )

        if permutation_comparison is not None:

            direct_max = (
                cell_comparison.get(
                    "max_length_relative_difference"
                )
            )

            permutation_max = (
                permutation_comparison.get(
                    "max_length_relative_difference"
                )
            )

            # Only use the permutation when it
            # actually improves the comparison.
            if (
                permutation_max is not None
                and (
                    direct_max is None
                    or permutation_max
                    < direct_max
                )
            ):
                # Keep the original comparison
                # for provenance/debugging.
                cell_comparison[
                    "direct_length_relative_differences"
                ] = cell_comparison.get(
                    "length_relative_differences"
                )

                cell_comparison[
                    "direct_max_length_relative_difference"
                ] = direct_max

                # Replace the effective length
                # comparison with the best
                # orthorhombic axis permutation.
                cell_comparison[
                    "length_relative_differences"
                ] = (
                    permutation_comparison[
                        "length_relative_differences"
                    ]
                )

                cell_comparison[
                    "max_length_relative_difference"
                ] = permutation_max

                cell_comparison[
                    "axis_mapping"
                ] = (
                    permutation_comparison[
                        "axis_mapping"
                    ]
                )

                cell_comparison[
                    "axis_permutation_applied"
                ] = True

                cell_comparison[
                    "comparison_mode"
                ] = (
                    "orthorhombic_axis_permutation"
                )

    # --------------------------------
    # Chemistry comparison
    # --------------------------------

    chemistry_comparison = (
        compare_chemistry(
            rruff_signature.get(
                "ideal_chemistry"
            ),
            candidate_structure.get(
                "formula"
            ),
        )
    )

    # --------------------------------
    # Combined comparison result
    # --------------------------------

    return {
        "sample_name_match":
            sample_name_match,

        "reference_name_match":
            reference_name_match,

        "space_group":
            space_group_comparison,

        "cell":
            cell_comparison,

        "chemistry":
            chemistry_comparison,
    }