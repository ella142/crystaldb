from pathlib import Path

import gemmi


def _clean_text(value):
    """Remove CIF quote characters and normalize missing values."""
    if value is None:
        return None

    value = str(value).strip()

    if value in {"", ".", "?"}:
        return None

    if (
        len(value) >= 2
        and value[0] == value[-1]
        and value[0] in {"'", '"'}
    ):
        value = value[1:-1]

    return value


def _to_float(value):
    """Convert a CIF numeric value to float when possible."""
    value = _clean_text(value)

    if value is None:
        return None

    try:
        return float(value)
    except ValueError:
        return None


def parse_cif(cif_path):
    cif_path = Path(cif_path)

    doc = gemmi.cif.read_file(str(cif_path))
    block = doc.sole_block()

    atoms = []

    atom_table = block.find(
        [
            "_atom_site_label",
            "_atom_site_fract_x",
            "_atom_site_fract_y",
            "_atom_site_fract_z",
        ]
    )

    for row in atom_table:
        atoms.append(
            {
                "label": _clean_text(row[0]),
                "fract_x": _to_float(row[1]),
                "fract_y": _to_float(row[2]),
                "fract_z": _to_float(row[3]),
            }
        )

    authors = [
        _clean_text(value)
        for value in block.find_values(
            "_publ_author_name"
        )
    ]

    structure = {
        "data_block": block.name,

        "formula": _clean_text(
            block.find_value("_chemical_formula_sum")
        ),

        "mineral_name": _clean_text(
            block.find_value("_chemical_name_mineral")
        ),

        "space_group": _clean_text(
            block.find_value(
                "_symmetry_space_group_name_H-M"
            )
        ),

        "cell_parameters": {
            "a": _to_float(
                block.find_value("_cell_length_a")
            ),
            "b": _to_float(
                block.find_value("_cell_length_b")
            ),
            "c": _to_float(
                block.find_value("_cell_length_c")
            ),
            "alpha": _to_float(
                block.find_value("_cell_angle_alpha")
            ),
            "beta": _to_float(
                block.find_value("_cell_angle_beta")
            ),
            "gamma": _to_float(
                block.find_value("_cell_angle_gamma")
            ),
            "volume": _to_float(
                block.find_value("_cell_volume")
            ),
        },

        "atoms": atoms,
        "atom_count": len(atoms),

        "source_file": cif_path.name,

        "publication": {
            "authors": authors,

            "title": _clean_text(
                block.find_value(
                    "_publ_section_title"
                )
            ),

            "journal": _clean_text(
                block.find_value(
                    "_journal_name_full"
                )
            ),

            "year": _clean_text(
                block.find_value(
                    "_journal_year"
                )
            ),

            "volume": _clean_text(
                block.find_value(
                    "_journal_volume"
                )
            ),

            "page_first": _clean_text(
                block.find_value(
                    "_journal_page_first"
                )
            ),

            "page_last": _clean_text(
                block.find_value(
                    "_journal_page_last"
                )
            ),
        },
    }

    return structure