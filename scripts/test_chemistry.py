from pprint import pprint

from crystaldb.matching.chemistry import (
    compare_chemistry,
)


tests = [
    (
        "Acanthite same formula",
        "Ag_2_S",
        "Ag2 S",
    ),

    (
        "Same formula multiplied",
        "Ag2S",
        "Ag4S2",
    ),

    (
        "Clearly wrong chemistry",
        "Ag2S",
        "Na Ca2 Fe5 Si8 O24 H2",
    ),

    (
        "Actinolite complex formula",
        (
            "[box]Ca_2_"
            "(Mg_4.5-2.5_Fe^2+^_0.5-2.5_)"
            "Si_8_O_22_(OH)_2_"
        ),
        "Na Ca2 Fe5 Si8 O24 H2",
    ),

    (
        "Tremolite complex formula",
        (
            "[box]Ca_2_"
            "(Mg_5.0-4.5_Fe^2+^_0.0-0.5_)"
            "Si_8_O_22_(OH)_2_"
        ),
        "Na Ca2 Fe5 Si8 O24 H2",
    ),
]


for name, formula_a, formula_b in tests:
    print("\n================================")
    print(name)
    print("================================")

    pprint(
        compare_chemistry(
            formula_a,
            formula_b,
        )
    )