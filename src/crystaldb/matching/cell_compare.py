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