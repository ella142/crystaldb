import json
from math import asin, cos, degrees, radians, sin
from pathlib import Path
from statistics import mean, median

import gemmi

from crystaldb.mongo import get_database


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RESOLUTION_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_experimental_resolution_v1.json"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "reports"
    / "figures"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


SAMPLE_ID = "R040017"

SELECTED_COD_ID = "9007533"
ALTERNATIVE_COD_ID = "9009082"

CU_WAVELENGTH = 1.541838

SEARCH_WINDOW = 0.30
TOP_N = 15


# ============================================================
# Basic helpers
# ============================================================

def normalize(values):
    values = [
        float(value)
        for value in values
    ]

    minimum = min(values)

    shifted = [
        value - minimum
        for value in values
    ]

    maximum = max(shifted)

    if maximum <= 0:
        return [
            0.0
            for _ in shifted
        ]

    return [
        value
        / maximum
        * 100.0
        for value in shifted
    ]


def two_theta_from_d(
    d_spacing,
    wavelength,
):
    argument = (
        wavelength
        / (
            2.0
            * float(d_spacing)
        )
    )

    if (
        argument <= 0
        or argument > 1
    ):
        return None

    return (
        2.0
        * degrees(
            asin(argument)
        )
    )


def multiplicity(
    spacegroup,
    hkl,
):
    equivalents = set()

    for op in spacegroup.operations():

        transformed = tuple(
            int(value)
            for value
            in op.apply_to_hkl(
                hkl
            )
        )

        equivalents.add(
            transformed
        )

        equivalents.add(
            tuple(
                -value
                for value
                in transformed
            )
        )

    return len(equivalents)


def lorentz_polarization(
    two_theta,
):
    theta = radians(
        two_theta / 2.0
    )

    two_theta_rad = radians(
        two_theta
    )

    denominator = (
        sin(theta) ** 2
        * cos(theta)
    )

    if denominator <= 0:
        return 0.0

    return (
        1.0
        + cos(two_theta_rad) ** 2
    ) / denominator


# ============================================================
# CIF -> powder reflections
# ============================================================

def calculate_reflections(
    cif_path,
    wavelength,
    raw_min,
    raw_max,
):
    document = gemmi.cif.read_file(
        str(cif_path)
    )

    block = document.sole_block()

    structure = (
        gemmi.make_small_structure_from_block(
            block
        )
    )

    spacegroup = structure.spacegroup

    if spacegroup is None:

        structure.determine_and_set_spacegroup()

        spacegroup = structure.spacegroup

    theta_max = radians(
        raw_max / 2.0
    )

    theta_min = radians(
        raw_min / 2.0
    )

    d_min = (
        wavelength
        / (
            2.0
            * sin(theta_max)
        )
    )

    d_max = (
        wavelength
        / (
            2.0
            * sin(theta_min)
        )
    )

    miller_array = gemmi.make_miller_array(
        structure.cell,
        spacegroup,
        d_min,
        d_max,
        True,
    )

    sf_calculator = (
        gemmi.StructureFactorCalculatorX(
            structure.cell
        )
    )

    reflections = []

    for hkl_array in miller_array:

        hkl = tuple(
            int(value)
            for value in hkl_array
        )

        if (
            spacegroup.operations()
            .is_systematically_absent(
                hkl
            )
        ):
            continue

        d_spacing = (
            structure.cell.calculate_d(
                hkl
            )
        )

        two_theta = (
            two_theta_from_d(
                d_spacing,
                wavelength,
            )
        )

        if two_theta is None:
            continue

        if not (
            raw_min
            <= two_theta
            <= raw_max
        ):
            continue

        sf = (
            sf_calculator
            .calculate_sf_from_small_structure(
                structure,
                hkl,
            )
        )

        f_squared = (
            abs(sf) ** 2
        )

        mult = multiplicity(
            spacegroup,
            hkl,
        )

        lp = lorentz_polarization(
            two_theta
        )

        intensity = (
            f_squared
            * mult
            * lp
        )

        reflections.append(
            {
                "hkl": hkl,
                "two_theta": two_theta,
                "d_spacing": d_spacing,
                "intensity": intensity,
            }
        )

    maximum = max(
        item["intensity"]
        for item in reflections
    )

    for item in reflections:

        item["relative_intensity"] = (
            item["intensity"]
            / maximum
            * 100.0
        )

    return {
        "structure": structure,
        "spacegroup": spacegroup,
        "reflections": reflections,
    }


# ============================================================
# Match theoretical positions to RAW
# ============================================================

def match_to_experiment(
    reflections,
    raw_x,
    raw_y,
):
    strongest = sorted(
        reflections,
        key=lambda item:
            item["relative_intensity"],
        reverse=True,
    )[:TOP_N]

    matches = []

    for item in strongest:

        target = item[
            "two_theta"
        ]

        local = [
            (
                angle,
                intensity,
            )
            for angle, intensity
            in zip(
                raw_x,
                raw_y,
            )
            if abs(
                angle - target
            ) <= SEARCH_WINDOW
        ]

        if not local:
            observed_angle = None
            observed_intensity = None
            delta = None

        else:
            (
                observed_angle,
                observed_intensity,
            ) = max(
                local,
                key=lambda pair:
                    pair[1],
            )

            delta = (
                observed_angle
                - target
            )

        matches.append(
            {
                **item,
                "observed_two_theta":
                    observed_angle,
                "observed_intensity":
                    observed_intensity,
                "delta_two_theta":
                    delta,
            }
        )

    return matches


def summarize_matches(
    matches,
):
    valid = [
        item
        for item in matches
        if item["delta_two_theta"]
        is not None
    ]

    abs_delta = [
        abs(
            item[
                "delta_two_theta"
            ]
        )
        for item in valid
    ]

    weights = [
        item[
            "relative_intensity"
        ]
        for item in valid
    ]

    if not valid:
        return None

    weighted_mean = (
        sum(
            delta * weight
            for delta, weight
            in zip(
                abs_delta,
                weights,
            )
        )
        / sum(weights)
    )

    return {
        "count":
            len(valid),

        "mean_abs_delta":
            mean(abs_delta),

        "median_abs_delta":
            median(abs_delta),

        "max_abs_delta":
            max(abs_delta),

        "weighted_mean_abs_delta":
            weighted_mean,

        "within_0_05":
            sum(
                value <= 0.05
                for value in abs_delta
            ),

        "within_0_10":
            sum(
                value <= 0.10
                for value in abs_delta
            ),

        "within_0_20":
            sum(
                value <= 0.20
                for value in abs_delta
            ),
    }


# ============================================================
# Compare theoretical peak positions
# ============================================================

def theoretical_overlap(
    reflections_a,
    reflections_b,
):
    top_a = sorted(
        reflections_a,
        key=lambda item:
            item[
                "relative_intensity"
            ],
        reverse=True,
    )[:TOP_N]

    top_b = sorted(
        reflections_b,
        key=lambda item:
            item[
                "relative_intensity"
            ],
        reverse=True,
    )[:TOP_N]

    distances = []

    for source, target in [
        (
            top_a,
            reflections_b,
        ),
        (
            top_b,
            reflections_a,
        ),
    ]:

        for item in source:

            nearest = min(
                abs(
                    item["two_theta"]
                    - other["two_theta"]
                )
                for other in target
            )

            distances.append(
                nearest
            )

    return {
        "median_nearest_difference":
            median(distances),

        "mean_nearest_difference":
            mean(distances),

        "max_nearest_difference":
            max(distances),

        "within_0_02":
            sum(
                value <= 0.02
                for value in distances
            ),

        "within_0_05":
            sum(
                value <= 0.05
                for value in distances
            ),

        "comparison_count":
            len(distances),
    }


# ============================================================
# Load experimental profile
# ============================================================

data = json.loads(
    RESOLUTION_FILE.read_text(
        encoding="utf-8"
    )
)

record = next(
    item
    for item in data["records"]
    if item["sample_id"]
    == SAMPLE_ID
)


db = get_database(
    database_name="rruff"
)

measurement_id = (
    record["measurement"][
        "filename_sample_id"
    ]
)

raw = db.xy_raw.find_one(
    {
        "filename_sample_id":
            measurement_id
    }
)

raw_x = [
    float(value)
    for value
    in raw["xrd"]["two_theta"]
]

raw_y = normalize(
    raw["xrd"]["intensity"]
)

raw_min = raw_x[0]
raw_max = raw_x[-1]


# ============================================================
# Calculate both CIFs
# ============================================================

selected_path = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "cod"
    / f"{SELECTED_COD_ID}.cif"
)

alternative_path = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "cod"
    / f"{ALTERNATIVE_COD_ID}.cif"
)


selected_result = (
    calculate_reflections(
        selected_path,
        CU_WAVELENGTH,
        raw_min,
        raw_max,
    )
)

alternative_result = (
    calculate_reflections(
        alternative_path,
        CU_WAVELENGTH,
        raw_min,
        raw_max,
    )
)


selected_matches = (
    match_to_experiment(
        selected_result[
            "reflections"
        ],
        raw_x,
        raw_y,
    )
)

alternative_matches = (
    match_to_experiment(
        alternative_result[
            "reflections"
        ],
        raw_x,
        raw_y,
    )
)


selected_summary = (
    summarize_matches(
        selected_matches
    )
)

alternative_summary = (
    summarize_matches(
        alternative_matches
    )
)

overlap = theoretical_overlap(
    selected_result[
        "reflections"
    ],
    alternative_result[
        "reflections"
    ],
)


# ============================================================
# Print comparison
# ============================================================

print()
print("=" * 96)
print(
    "SELECTED vs ALTERNATIVE CIF "
    "DIFFRACTION COMPARISON"
)
print("=" * 96)

print(
    "sample_id:        ",
    SAMPLE_ID,
)

print(
    "mineral:          ",
    record.get("mineral"),
)

print(
    "selected COD:     ",
    SELECTED_COD_ID,
)

print(
    "alternative COD:  ",
    ALTERNATIVE_COD_ID,
)

print(
    "wavelength:       ",
    CU_WAVELENGTH,
)

print()


def print_cell(
    label,
    structure,
):
    cell = structure.cell

    print(
        f"{label:<14}",
        (
            f"a={cell.a:.5f} "
            f"b={cell.b:.5f} "
            f"c={cell.c:.5f} "
            f"alpha={cell.alpha:.3f} "
            f"beta={cell.beta:.3f} "
            f"gamma={cell.gamma:.3f}"
        ),
    )


print_cell(
    "Selected cell:",
    selected_result[
        "structure"
    ],
)

print_cell(
    "Alternative:",
    alternative_result[
        "structure"
    ],
)


print()
print("-" * 96)
print("EXPERIMENTAL PEAK-POSITION AGREEMENT")
print("-" * 96)

print(
    f"{'Metric':<34}"
    f"{'Selected':>16}"
    f"{'Alternative':>16}"
)

for label, key in [
    (
        "Mean |Delta 2theta|",
        "mean_abs_delta",
    ),
    (
        "Median |Delta 2theta|",
        "median_abs_delta",
    ),
    (
        "Weighted mean |Delta|",
        "weighted_mean_abs_delta",
    ),
    (
        "Maximum |Delta 2theta|",
        "max_abs_delta",
    ),
]:

    print(
        f"{label:<34}"
        f"{selected_summary[key]:>16.5f}"
        f"{alternative_summary[key]:>16.5f}"
    )


for label, key in [
    (
        "Top peaks within 0.05 deg",
        "within_0_05",
    ),
    (
        "Top peaks within 0.10 deg",
        "within_0_10",
    ),
    (
        "Top peaks within 0.20 deg",
        "within_0_20",
    ),
]:

    print(
        f"{label:<34}"
        f"{selected_summary[key]:>16d}"
        f"{alternative_summary[key]:>16d}"
    )


print()
print("-" * 96)
print("THEORETICAL CIF-vs-CIF PEAK OVERLAP")
print("-" * 96)

print(
    "Symmetric comparisons:          ",
    overlap[
        "comparison_count"
    ],
)

print(
    "Median nearest peak difference: ",
    f"{overlap['median_nearest_difference']:.5f} deg",
)

print(
    "Mean nearest peak difference:   ",
    f"{overlap['mean_nearest_difference']:.5f} deg",
)

print(
    "Maximum nearest difference:     ",
    f"{overlap['max_nearest_difference']:.5f} deg",
)

print(
    "Within 0.02 deg:                ",
    overlap[
        "within_0_02"
    ],
)

print(
    "Within 0.05 deg:                ",
    overlap[
        "within_0_05"
    ],
)


# ============================================================
# Individual top-peak table
# ============================================================

print()
print("=" * 96)
print("SELECTED CIF TOP PEAK MATCHES")
print("=" * 96)

print(
    f"{'Rank':<6}"
    f"{'hkl':<16}"
    f"{'Calc':>11}"
    f"{'Icalc':>10}"
    f"{'Observed':>12}"
    f"{'Delta':>11}"
)

for rank, item in enumerate(
    selected_matches,
    start=1,
):

    print(
        f"{rank:<6}"
        f"{str(item['hkl']):<16}"
        f"{item['two_theta']:>11.4f}"
        f"{item['relative_intensity']:>10.2f}"
        f"{item['observed_two_theta']:>12.4f}"
        f"{item['delta_two_theta']:>11.4f}"
    )


print()
print("=" * 96)
print("ALTERNATIVE CIF TOP PEAK MATCHES")
print("=" * 96)

print(
    f"{'Rank':<6}"
    f"{'hkl':<16}"
    f"{'Calc':>11}"
    f"{'Icalc':>10}"
    f"{'Observed':>12}"
    f"{'Delta':>11}"
)

for rank, item in enumerate(
    alternative_matches,
    start=1,
):

    print(
        f"{rank:<6}"
        f"{str(item['hkl']):<16}"
        f"{item['two_theta']:>11.4f}"
        f"{item['relative_intensity']:>10.2f}"
        f"{item['observed_two_theta']:>12.4f}"
        f"{item['delta_two_theta']:>11.4f}"
    )


print()
print("=" * 96)
print(
    "IMPORTANT: No pass/fail threshold "
    "is applied in this experiment."
)
print("=" * 96)

