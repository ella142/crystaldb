import json
from math import (
    asin,
    cos,
    degrees,
    radians,
    sin,
)
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

SAMPLE_ID = "R040014"

CU_WAVELENGTH = 1.541838
MO_WAVELENGTH = 0.710730

SEARCH_WINDOW = 0.30
TOP_N = 15


# ============================================================
# Helpers
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
        value / maximum * 100.0
        for value in shifted
    ]


def implied_wavelength(
    d_spacing,
    two_theta,
):
    theta = radians(
        float(two_theta) / 2.0
    )

    return (
        2.0
        * float(d_spacing)
        * sin(theta)
    )


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
# CIF -> theoretical powder reflections
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

    miller_array = (
        gemmi.make_miller_array(
            structure.cell,
            spacegroup,
            d_min,
            d_max,
            True,
        )
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
            for value
            in hkl_array
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
                "hkl":
                    hkl,

                "two_theta":
                    two_theta,

                "d_spacing":
                    d_spacing,

                "intensity":
                    intensity,
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
        "structure":
            structure,

        "spacegroup":
            spacegroup,

        "reflections":
            reflections,
    }


# ============================================================
# Theoretical -> experimental matching
# ============================================================

def match_to_experiment(
    reflections,
    raw_x,
    raw_y,
):
    strongest = sorted(
        reflections,
        key=lambda item:
            item[
                "relative_intensity"
            ],
        reverse=True,
    )[:TOP_N]

    matches = []

    for reflection in strongest:

        calculated = reflection[
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
                angle - calculated
            )
            <= SEARCH_WINDOW
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
                key=lambda item:
                    item[1],
            )

            delta = (
                observed_angle
                - calculated
            )

        matches.append(
            {
                **reflection,

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
        if item[
            "delta_two_theta"
        ] is not None
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
        "mean_abs_delta":
            mean(abs_delta),

        "median_abs_delta":
            median(abs_delta),

        "weighted_mean_abs_delta":
            weighted_mean,

        "max_abs_delta":
            max(abs_delta),

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
# Candidate-vs-candidate theoretical separation
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
                    item[
                        "two_theta"
                    ]
                    - other[
                        "two_theta"
                    ]
                )
                for other in target
            )

            distances.append(
                nearest
            )

    return {
        "comparison_count":
            len(distances),

        "mean":
            mean(distances),

        "median":
            median(distances),

        "maximum":
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

        "within_0_10":
            sum(
                value <= 0.10
                for value in distances
            ),
    }


# ============================================================
# Load frozen group result
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

resolution = (
    record[
        "structure_resolution"
    ]
)

if (
    resolution[
        "resolution_level"
    ]
    != "group"
):
    raise RuntimeError(
        "Expected a group-level "
        "resolution record."
    )

candidates = (
    resolution[
        "bibliographic_candidates"
    ]
)

if len(candidates) < 2:
    raise RuntimeError(
        "Expected multiple "
        "bibliographic candidates."
    )


# ============================================================
# Experimental RAW
# ============================================================

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

dif = db.dif.find_one(
    {
        "sample_id":
            SAMPLE_ID
    }
)

raw_x = [
    float(value)
    for value
    in raw[
        "xrd"
    ][
        "two_theta"
    ]
]

raw_y = normalize(
    raw[
        "xrd"
    ][
        "intensity"
    ]
)

raw_min = raw_x[0]
raw_max = raw_x[-1]


# ============================================================
# Derive validation wavelength
# ============================================================

implied_values = []

for peak in (
    dif.get(
        "diffraction",
        {},
    ).get(
        "peaks",
        [],
    )
):

    d_spacing = peak.get(
        "d_spacing"
    )

    two_theta = peak.get(
        "two_theta"
    )

    if (
        d_spacing is None
        or two_theta is None
    ):
        continue

    implied_values.append(
        implied_wavelength(
            d_spacing,
            two_theta,
        )
    )


implied_median = median(
    implied_values
)

if (
    abs(
        implied_median
        - CU_WAVELENGTH
    )
    <
    abs(
        implied_median
        - MO_WAVELENGTH
    )
):

    radiation_class = "Cu-like"
    wavelength = CU_WAVELENGTH

else:

    radiation_class = "Mo-like"
    wavelength = MO_WAVELENGTH


# ============================================================
# Calculate all bibliography-supported CIFs
# ============================================================

candidate_results = []


for candidate in candidates:

    source_id = candidate[
        "source_id"
    ]

    cif_path = (
        PROJECT_ROOT
        / candidate[
            "file_path"
        ]
    )

    calculated = (
        calculate_reflections(
            cif_path,
            wavelength,
            raw_min,
            raw_max,
        )
    )

    matches = (
        match_to_experiment(
            calculated[
                "reflections"
            ],
            raw_x,
            raw_y,
        )
    )

    summary = (
        summarize_matches(
            matches
        )
    )

    candidate_results.append(
        {
            "source_id":
                source_id,

            "structure":
                calculated[
                    "structure"
                ],

            "spacegroup":
                calculated[
                    "spacegroup"
                ],

            "reflections":
                calculated[
                    "reflections"
                ],

            "matches":
                matches,

            "summary":
                summary,
        }
    )


# ============================================================
# Main output
# ============================================================

print()
print("=" * 104)
print(
    "BUSTAMITE BIBLIOGRAPHIC GROUP "
    "DIFFRACTION PILOT"
)
print("=" * 104)

print(
    "sample_id:                 ",
    SAMPLE_ID,
)

print(
    "mineral:                   ",
    record.get("mineral"),
)

print(
    "measurement_id:            ",
    measurement_id,
)

print(
    "group candidate count:     ",
    len(candidate_results),
)

print(
    "Bragg-implied wavelength:  ",
    f"{implied_median:.6f}",
)

print(
    "radiation class:           ",
    radiation_class,
)

print(
    "validation wavelength:     ",
    f"{wavelength:.6f}",
)

print(
    "RAW range:                 ",
    f"{raw_min:.3f}",
    "->",
    f"{raw_max:.3f}",
)

print()


# ============================================================
# Candidate cells
# ============================================================

print("-" * 104)
print("CANDIDATE CRYSTALLOGRAPHY")
print("-" * 104)

for item in candidate_results:

    cell = item[
        "structure"
    ].cell

    print(
        item["source_id"],
        "| SG =",
        item[
            "spacegroup"
        ].xhm(),
        "| cell =",
        (
            f"{cell.a:.5f}, "
            f"{cell.b:.5f}, "
            f"{cell.c:.5f}, "
            f"{cell.alpha:.3f}, "
            f"{cell.beta:.3f}, "
            f"{cell.gamma:.3f}"
        ),
        "| reflections =",
        len(
            item[
                "reflections"
            ]
        ),
    )


# ============================================================
# Experimental agreement summary
# ============================================================

print()
print("-" * 104)
print("EXPERIMENTAL PEAK-POSITION AGREEMENT")
print("-" * 104)

print(
    f"{'COD':<12}"
    f"{'Mean |d2theta|':>17}"
    f"{'Median':>12}"
    f"{'Weighted':>12}"
    f"{'Max':>12}"
    f"{'<=0.05':>10}"
    f"{'<=0.10':>10}"
    f"{'<=0.20':>10}"
)


for item in candidate_results:

    summary = item[
        "summary"
    ]

    print(
        f"{item['source_id']:<12}"
        f"{summary['mean_abs_delta']:>17.5f}"
        f"{summary['median_abs_delta']:>12.5f}"
        f"{summary['weighted_mean_abs_delta']:>12.5f}"
        f"{summary['max_abs_delta']:>12.5f}"
        f"{summary['within_0_05']:>10d}"
        f"{summary['within_0_10']:>10d}"
        f"{summary['within_0_20']:>10d}"
    )


# ============================================================
# Pairwise candidate separability
# ============================================================

print()
print("-" * 104)
print("PAIRWISE THEORETICAL PEAK SEPARATION")
print("-" * 104)

print(
    f"{'Pair':<27}"
    f"{'Mean':>12}"
    f"{'Median':>12}"
    f"{'Max':>12}"
    f"{'<=0.02':>10}"
    f"{'<=0.05':>10}"
    f"{'<=0.10':>10}"
)


for left_index in range(
    len(candidate_results)
):

    for right_index in range(
        left_index + 1,
        len(candidate_results),
    ):

        left = candidate_results[
            left_index
        ]

        right = candidate_results[
            right_index
        ]

        overlap = theoretical_overlap(
            left[
                "reflections"
            ],
            right[
                "reflections"
            ],
        )

        pair_name = (
            f"{left['source_id']} vs "
            f"{right['source_id']}"
        )

        print(
            f"{pair_name:<27}"
            f"{overlap['mean']:>12.5f}"
            f"{overlap['median']:>12.5f}"
            f"{overlap['maximum']:>12.5f}"
            f"{overlap['within_0_02']:>10d}"
            f"{overlap['within_0_05']:>10d}"
            f"{overlap['within_0_10']:>10d}"
        )


# ============================================================
# Top peaks for each candidate
# ============================================================

for item in candidate_results:

    print()
    print("=" * 104)
    print(
        f"COD {item['source_id']} "
        f"TOP {TOP_N} PEAK MATCHES"
    )
    print("=" * 104)

    print(
        f"{'Rank':<6}"
        f"{'hkl':<16}"
        f"{'Calc':>11}"
        f"{'Icalc':>10}"
        f"{'Observed':>12}"
        f"{'Iobs':>10}"
        f"{'Delta':>11}"
    )

    for rank, peak in enumerate(
        item["matches"],
        start=1,
    ):

        print(
            f"{rank:<6}"
            f"{str(peak['hkl']):<16}"
            f"{peak['two_theta']:>11.4f}"
            f"{peak['relative_intensity']:>10.2f}"
            f"{peak['observed_two_theta']:>12.4f}"
            f"{peak['observed_intensity']:>10.2f}"
            f"{peak['delta_two_theta']:>11.4f}"
        )


print()
print("=" * 104)
print(
    "IMPORTANT: this pilot compares "
    "candidate separability; it does not "
    "force a winning CIF."
)
print("=" * 104)

