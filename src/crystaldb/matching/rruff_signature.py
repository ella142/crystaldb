def build_rruff_signature(
    dif_doc,
    ideal_chemistry=None,
):
    """
    Convert one RRUFF DIF MongoDB document into
    a compact structure-matching signature.
    """

    crystal = dif_doc.get("crystal_structure") or {}
    cell = crystal.get("cell_parameters") or {}

    signature = {
        "sample_id": dif_doc.get("sample_id"),

        # 样品侧名称
        "sample_mineral": dif_doc.get("filename_mineral"),

        # DIF 所使用的参考结构名称
        "reference_structure_name": dif_doc.get("mineral"),

        # RRUFF ideal chemistry
        "ideal_chemistry": ideal_chemistry,

        "space_group": crystal.get("space_group"),

        "cell_parameters": {
            "a": cell.get("a"),
            "b": cell.get("b"),
            "c": cell.get("c"),
            "alpha": cell.get("alpha"),
            "beta": cell.get("beta"),
            "gamma": cell.get("gamma"),
        },

        "atom_count": crystal.get("atom_count", 0),

        "references": dif_doc.get("references") or [],
    }

    return signature


def get_rruff_ideal_chemistry(
    rruff_db,
    sample_id,
):
    """
    Get RRUFF IDEAL CHEMISTRY for one sample.

    Currently uses xy_raw because this field is known
    to be present in its metadata.
    """

    doc = rruff_db.xy_raw.find_one(
        {
            "sample_id": sample_id,
            "metadata.IDEAL CHEMISTRY": {
                "$exists": True,
                "$nin": [None, ""],
            },
        },
        {
            "_id": 0,
            "metadata.IDEAL CHEMISTRY": 1,
        },
    )

    if doc is None:
        return None

    return (
        doc
        .get("metadata", {})
        .get("IDEAL CHEMISTRY")
    )