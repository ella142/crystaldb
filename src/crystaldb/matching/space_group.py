import gemmi


def resolve_space_group(space_group):
    """
    Resolve a space-group symbol using Gemmi.

    Returns a normalized crystallographic representation.
    """

    if space_group is None:
        return {
            "recognized": False,
            "input": None,
        }

    original = str(space_group).strip()

    # RRUFF may contain CIF-style underscores such as P2_1/n.
    cleaned = original.replace("_", "")

    # Known RRUFF shorthand that Gemmi does not resolve directly.
    space_group_aliases = {
        "P21/b": "P 21/b 1 1",
    }

    resolved_name = space_group_aliases.get(
        cleaned,
        cleaned,
    )

    sg = gemmi.find_spacegroup_by_name(
        resolved_name
    )
    if sg is None:
        return {
            "recognized": False,
            "input": original,
            "cleaned": resolved_name,
        }

    return {
        "recognized": True,
        "input": original,
        "cleaned": resolved_name,
        "number": sg.number,
        "hm": sg.hm,
        "xhm": sg.xhm(),
        "hall": sg.hall,
        "short_name": sg.short_name(),
    }


def compare_space_groups(space_group_a, space_group_b):
    """
    Compare two space groups after Gemmi resolution.
    """

    a = resolve_space_group(space_group_a)
    b = resolve_space_group(space_group_b)

    if not a["recognized"] or not b["recognized"]:
        return {
            "equivalent": None,
            "same_number": None,
            "same_operations": None,
            "a": a,
            "b": b,
        }

    sg_a = gemmi.find_spacegroup_by_name(a["cleaned"])
    sg_b = gemmi.find_spacegroup_by_name(b["cleaned"])

    same_number = sg_a.number == sg_b.number
    same_operations = sg_a.operations() == sg_b.operations()

    return {
        "equivalent": same_operations,
        "same_number": same_number,
        "same_operations": same_operations,
        "a": a,
        "b": b,
    }
