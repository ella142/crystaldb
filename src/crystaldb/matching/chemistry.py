import re
from math import isclose


ELEMENT_PATTERN = re.compile(
    r"[A-Z][a-z]?"
)

SIMPLE_TOKEN_PATTERN = re.compile(
    r"([A-Z][a-z]?)(\d+(?:\.\d+)?)?"
)


def extract_elements(formula):
    """
    Extract element symbols from a formula.

    Examples
    --------
    Ag_2_S
        -> {"Ag", "S"}

    Ag2 S
        -> {"Ag", "S"}
    """

    if formula is None:
        return set()

    formula = str(formula).strip()

    if not formula:
        return set()

    return set(
        ELEMENT_PATTERN.findall(formula)
    )


def chemistry_signature(formula):
    elements = extract_elements(formula)

    return {
        "formula": formula,
        "elements": sorted(elements),
        "element_count": len(elements),
    }


def _is_complex_formula(formula):
    """
    Return True when the formula contains notation that
    crystaldb v0.3 does not yet try to interpret exactly.

    Examples:
    - solid-solution ranges
    - oxidation-state notation
    - vacancies
    - grouped OH / parentheses
    """

    if formula is None:
        return True

    value = str(formula)

    complex_markers = [
        "[",
        "]",
        "(",
        ")",
        "^",
        ";",
    ]

    if any(
        marker in value
        for marker in complex_markers
    ):
        return True

    # Example:
    # Mg_5.0-4.5_
    if re.search(
        r"\d+(?:\.\d+)?-\d+(?:\.\d+)?",
        value,
    ):
        return True

    return False


def parse_simple_composition(formula):
    """
    Parse simple chemical formulas into element amounts.

    Examples
    --------
    Ag_2_S
        -> {"Ag": 2.0, "S": 1.0}

    Ag2 S
        -> {"Ag": 2.0, "S": 1.0}

    Na Ca2 Fe5 Si8 O24 H2
        -> {
            "Na": 1,
            "Ca": 2,
            "Fe": 5,
            "Si": 8,
            "O": 24,
            "H": 2,
        }

    Complex mineral formulas return None.
    """

    if formula is None:
        return None

    value = str(formula).strip()

    if not value:
        return None

    if _is_complex_formula(value):
        return None

    # Remove RRUFF formatting separators.
    cleaned = (
        value
        .replace("_", "")
        .replace(" ", "")
    )

    tokens = list(
        SIMPLE_TOKEN_PATTERN.finditer(cleaned)
    )

    if not tokens:
        return None

    # Make sure the whole formula was understood.
    reconstructed = "".join(
        match.group(0)
        for match in tokens
    )

    if reconstructed != cleaned:
        return None

    composition = {}

    for match in tokens:
        element = match.group(1)

        amount_text = match.group(2)

        amount = (
            float(amount_text)
            if amount_text
            else 1.0
        )

        composition[element] = (
            composition.get(element, 0.0)
            + amount
        )

    return composition


def _normalized_composition(composition):
    """
    Normalize composition by total atom amount.

    This makes formulas comparable even if one formula
    is written as a multiple of another.
    """

    total = sum(composition.values())

    if total <= 0:
        return None

    return {
        element: amount / total
        for element, amount
        in composition.items()
    }


def compare_chemistry(
    formula_a,
    formula_b,
    tolerance=1e-3,
):
    """
    Compare two chemical formulas conservatively.

    Returns
    -------
    compatible = True
        Both formulas are simple and composition ratios
        agree.

    compatible = False
        Both formulas are simple and clearly disagree.

    compatible = None
        At least one formula uses complex mineral
        notation that v0.3 does not interpret exactly.
    """

    composition_a = parse_simple_composition(
        formula_a
    )

    composition_b = parse_simple_composition(
        formula_b
    )

    elements_a = extract_elements(formula_a)
    elements_b = extract_elements(formula_b)

    result = {
        "formula_a": formula_a,
        "formula_b": formula_b,

        "elements_a":
            sorted(elements_a),

        "elements_b":
            sorted(elements_b),

        "composition_a":
            composition_a,

        "composition_b":
            composition_b,

        "compatible": None,

        "reason": None,

        "rule_version":
            "0.3",
    }

    if (
        composition_a is None
        or composition_b is None
    ):
        result["reason"] = (
            "complex_or_unparsed_formula"
        )

        return result

    if (
        set(composition_a)
        != set(composition_b)
    ):
        result["compatible"] = False

        result["reason"] = (
            "different_element_set"
        )

        return result

    normalized_a = _normalized_composition(
        composition_a
    )

    normalized_b = _normalized_composition(
        composition_b
    )

    ratios_match = all(
        isclose(
            normalized_a[element],
            normalized_b[element],
            rel_tol=tolerance,
            abs_tol=tolerance,
        )
        for element in normalized_a
    )

    result["compatible"] = ratios_match

    result["reason"] = (
        "same_composition_ratio"
        if ratios_match
        else "different_composition_ratio"
    )

    return result


def chemistry_compatible(
    formula_a,
    formula_b,
):
    return compare_chemistry(
        formula_a,
        formula_b,
    )["compatible"]