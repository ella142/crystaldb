from crystaldb.matching.cell_compare import compare_cells
from crystaldb.matching.space_group import compare_space_groups
from crystaldb.matching.chemistry import  compare_chemistry



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
    # Unit-cell comparison
    # --------------------------------
    cell_comparison = compare_cells(
        rruff_signature.get(
            "cell_parameters"
        ) or {},
        candidate_structure.get(
            "cell_parameters"
        ) or {},
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