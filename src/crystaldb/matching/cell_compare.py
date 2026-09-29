from itertools import permutations

def relative_difference(value_a, value_b):
    """
    Relative difference using value_a as the reference.
    """
    if value_a is None or value_b is None:
        return None

    if value_a == 0:
        return None

    return abs(value_b - value_a) / abs(value_a)


def absolute_difference(value_a, value_b):
    if value_a is None or value_b is None:
        return None

    return abs(value_b - value_a)


def compare_cells(reference_cell, candidate_cell):
    """
    Compare two unit cells.

    Lengths:
        a, b, c -> relative difference

    Angles:
        alpha, beta, gamma -> absolute difference in degrees
    """

    length_keys = ["a", "b", "c"]
    angle_keys = ["alpha", "beta", "gamma"]

    length_differences = {}
    angle_differences = {}

    for key in length_keys:
        length_differences[key] = relative_difference(
            reference_cell.get(key),
            candidate_cell.get(key),
        )

    for key in angle_keys:
        angle_differences[key] = absolute_difference(
            reference_cell.get(key),
            candidate_cell.get(key),
        )

    valid_length_diffs = [
        value
        for value in length_differences.values()
        if value is not None
    ]

    valid_angle_diffs = [
        value
        for value in angle_differences.values()
        if value is not None
    ]

    return {
        "length_relative_differences": length_differences,
        "angle_absolute_differences": angle_differences,

        "max_length_relative_difference": (
            max(valid_length_diffs)
            if valid_length_diffs
            else None
        ),

        "max_angle_difference": (
            max(valid_angle_diffs)
            if valid_angle_diffs
            else None
        ),
    }

def is_orthorhombic_cell(
    cell,
    angle_tolerance=0.5,
):
    """
    Check whether a cell is approximately orthorhombic.
    """

    for key in ["alpha", "beta", "gamma"]:
        value = cell.get(key)

        if value is None:
            return False

        if abs(value - 90.0) > angle_tolerance:
            return False

    return True


def compare_orthorhombic_axis_permutations(
    reference_cell,
    candidate_cell,
):
    """
    Compare two approximately orthorhombic cells
    while allowing permutations of candidate a, b, c.
    """

    if not is_orthorhombic_cell(reference_cell):
        return None

    if not is_orthorhombic_cell(candidate_cell):
        return None

    reference_axes = ["a", "b", "c"]

    best_result = None

    for candidate_axes in permutations(
        ["a", "b", "c"]
    ):
        axis_mapping = dict(
            zip(
                reference_axes,
                candidate_axes,
            )
        )

        length_differences = {}

        for reference_axis in reference_axes:
            candidate_axis = axis_mapping[
                reference_axis
            ]

            length_differences[
                reference_axis
            ] = relative_difference(
                reference_cell.get(
                    reference_axis
                ),
                candidate_cell.get(
                    candidate_axis
                ),
            )

        valid_differences = [
            value
            for value in length_differences.values()
            if value is not None
        ]

        if len(valid_differences) != 3:
            continue

        max_difference = max(
            valid_differences
        )

        result = {
            "axis_mapping":
                axis_mapping,

            "length_relative_differences":
                length_differences,

            "max_length_relative_difference":
                max_difference,
        }

        if (
            best_result is None
            or max_difference
            < best_result[
                "max_length_relative_difference"
            ]
        ):
            best_result = result

    return best_result