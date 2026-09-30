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

SAMPLE_ID = "R040014"

CU_WAVELENGTH = 1.541838
MO_WAVELENGTH = 0.710730

TOP_THEORETICAL = 20

# Pilot-only settings.
INITIAL_WINDOW = 0.35
FINAL_WINDOW = 0.15

# Peak detection settings.
SMOOTH_RADIUS = 2
MIN_EXPERIMENTAL_INTENSITY = 1.0
MIN_PEAK_SEPARATION = 0.12
MAX_EXPERIMENTAL_PEAKS = 200


def normalize(values):
    values = [float(v) for v in values]

    minimum = min(values)
    shifted = [v - minimum for v in values]

    maximum = max(shifted)

    if maximum <= 0:
        return [0.0 for _ in shifted]

    return [
        value / maximum * 100.0
        for value in shifted
    ]


def smooth(values, radius):
    output = []
    n = len(values)

    for i in range(n):
        start = max(0, i - radius)
        end = min(n, i + radius + 1)

        output.append(
            sum(values[start:end])
            / (end - start)
        )

    return output


def detect_experimental_peaks(
    x,
    y,
):
    smoothed = smooth(
        y,
        SMOOTH_RADIUS,
    )

    candidates = []

    for i in range(
        1,
        len(smoothed) - 1,
    ):
        value = smoothed[i]

        if value < MIN_EXPERIMENTAL_INTENSITY:
            continue

        if (
            value >= smoothed[i - 1]
            and
            value > smoothed[i + 1]
        ):
            candidates.append(
                {
                    "two_theta": x[i],
                    "intensity": value,
                }
            )

    # Non-maximum suppression:
    # retain strong peaks without allowing
    # many noisy maxima at almost identical angles.
    candidates.sort(
        key=lambda item:
            item["intensity"],
        reverse=True,
    )

    retained = []

    for candidate in candidates:

        if any(
            abs(
                candidate["two_theta"]
                - existing["two_theta"]
            )
            < MIN_PEAK_SEPARATION
            for existing in retained
        ):
            continue

        retained.append(candidate)

        if (
            len(retained)
            >= MAX_EXPERIMENTAL_PEAKS
        ):
            break

    retained.sort(
        key=lambda item:
            item["two_theta"]
    )

    return retained


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
        / (2.0 * float(d_spacing))
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
            in op.apply_to_hkl(hkl)
        )

        equivalents.add(transformed)

        equivalents.add(
            tuple(
                -value
                for value in transformed
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


def calculate_reflections(
    cif_path,
    wavelength,
    raw_min,
    raw_max,
):
    document = gemmi.cif.read_file(
        str(cif_path)
    )

    structure = (
        gemmi.make_small_structure_from_block(
            document.sole_block()
        )
    )

    spacegroup = structure.spacegroup

    if spacegroup is None:
        structure.determine_and_set_spacegroup()
        spacegroup = structure.spacegroup

    d_min = (
        wavelength
        / (
            2.0
            * sin(
                radians(raw_max / 2.0)
            )
        )
    )

    d_max = (
        wavelength
        / (
            2.0
            * sin(
                radians(raw_min / 2.0)
            )
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
            for value in hkl_array
        )

        if (
            spacegroup.operations()
            .is_systematically_absent(hkl)
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

        if (
            two_theta is None
            or not (
                raw_min
                <= two_theta
                <= raw_max
            )
        ):
            continue

        sf = (
            sf_calculator
            .calculate_sf_from_small_structure(
                structure,
                hkl,
            )
        )

        intensity = (
            abs(sf) ** 2
            * multiplicity(
                spacegroup,
                hkl,
            )
            * lorentz_polarization(
                two_theta
            )
        )

        reflections.append(
            {
                "hkl": hkl,
                "two_theta": two_theta,
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


def weighted_median(
    values,
    weights,
):
    pairs = sorted(
        zip(values, weights),
        key=lambda item:
            item[0],
    )

    total = sum(weights)
    cumulative = 0.0

    for value, weight in pairs:

        cumulative += weight

        if cumulative >= total / 2.0:
            return value

    return pairs[-1][0]


def one_to_one_match(
    theoretical,
    experimental,
    shift,
    window,
):
    """
    Build all admissible theory/experiment
    pairs, then greedily accept the smallest
    residuals while preventing reuse of
    either theoretical or experimental peaks.
    """

    pair_candidates = []

    for theory_index, theory in enumerate(
        theoretical
    ):
        corrected = (
            theory["two_theta"]
            + shift
        )

        for exp_index, exp in enumerate(
            experimental
        ):
            residual = (
                exp["two_theta"]
                - corrected
            )

            if abs(residual) <= window:

                pair_candidates.append(
                    {
                        "theory_index":
                            theory_index,

                        "exp_index":
                            exp_index,

                        "residual":
                            residual,

                        "abs_residual":
                            abs(residual),

                        "theory_intensity":
                            theory[
                                "relative_intensity"
                            ],

                        "experimental_intensity":
                            exp["intensity"],
                    }
                )

    pair_candidates.sort(
        key=lambda item: (
            item["abs_residual"],
            -item["theory_intensity"],
            -item[
                "experimental_intensity"
            ],
        )
    )

    used_theory = set()
    used_experimental = set()

    matches = []

    for pair in pair_candidates:

        theory_index = pair[
            "theory_index"
        ]

        exp_index = pair[
            "exp_index"
        ]

        if theory_index in used_theory:
            continue

        if exp_index in used_experimental:
            continue

        used_theory.add(
            theory_index
        )

        used_experimental.add(
            exp_index
        )

        matches.append(
            {
                **pair,

                "theoretical":
                    theoretical[
                        theory_index
                    ],

                "experimental":
                    experimental[
                        exp_index
                    ],
            }
        )

    return matches


def estimate_zero_shift(
    theoretical,
    experimental,
):
    first_pass = one_to_one_match(
        theoretical,
        experimental,
        shift=0.0,
        window=INITIAL_WINDOW,
    )

    if not first_pass:
        return 0.0

    deltas = []

    weights = []

    for match in first_pass:

        theory = match[
            "theoretical"
        ]

        experimental_peak = match[
            "experimental"
        ]

        deltas.append(
            experimental_peak[
                "two_theta"
            ]
            - theory[
                "two_theta"
            ]
        )

        weights.append(
            theory[
                "relative_intensity"
            ]
        )

    return weighted_median(
        deltas,
        weights,
    )


def residual_slope(
    matches,
):
    """
    Linear slope of residual versus 2theta.

    After zero-shift correction,
    a remaining angle-dependent trend
    suggests that a simple constant offset
    cannot explain the mismatch.
    """

    if len(matches) < 2:
        return None

    x = [
        match["theoretical"][
            "two_theta"
        ]
        for match in matches
    ]

    y = [
        match["residual"]
        for match in matches
    ]

    mean_x = mean(x)
    mean_y = mean(y)

    denominator = sum(
        (value - mean_x) ** 2
        for value in x
    )

    if denominator == 0:
        return None

    numerator = sum(
        (
            x_value - mean_x
        )
        * (
            y_value - mean_y
        )
        for x_value, y_value
        in zip(x, y)
    )

    return (
        numerator
        / denominator
    )


def summarize(
    theoretical,
    experimental,
):
    zero_shift = estimate_zero_shift(
        theoretical,
        experimental,
    )

    matches = one_to_one_match(
        theoretical,
        experimental,
        shift=zero_shift,
        window=FINAL_WINDOW,
    )

    if not matches:
        return {
            "zero_shift":
                zero_shift,

            "matches":
                [],

            "matched_count":
                0,
        }

    abs_residuals = [
        match["abs_residual"]
        for match in matches
    ]

    weights = [
        match[
            "theory_intensity"
        ]
        for match in matches
    ]

    weighted_mean = (
        sum(
            residual * weight
            for residual, weight
            in zip(
                abs_residuals,
                weights,
            )
        )
        / sum(weights)
    )

    return {
        "zero_shift":
            zero_shift,

        "matches":
            matches,

        "matched_count":
            len(matches),

        "median_abs_residual":
            median(
                abs_residuals
            ),

        "mean_abs_residual":
            mean(
                abs_residuals
            ),

        "weighted_mean_abs_residual":
            weighted_mean,

        "max_abs_residual":
            max(
                abs_residuals
            ),

        "within_0_03":
            sum(
                value <= 0.03
                for value
                in abs_residuals
            ),

        "within_0_05":
            sum(
                value <= 0.05
                for value
                in abs_residuals
            ),

        "within_0_10":
            sum(
                value <= 0.10
                for value
                in abs_residuals
            ),

        "residual_slope":
            residual_slope(
                matches
            ),
    }


# ============================================================
# Load frozen group
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

candidates = (
    resolution[
        "bibliographic_candidates"
    ]
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
    for value in
    raw["xrd"]["two_theta"]
]

raw_y = normalize(
    raw["xrd"]["intensity"]
)

experimental_peaks = (
    detect_experimental_peaks(
        raw_x,
        raw_y,
    )
)

raw_min = raw_x[0]
raw_max = raw_x[-1]


# ============================================================
# Bragg-derived radiation
# ============================================================

implied = []

for peak in (
    dif.get(
        "diffraction",
        {},
    ).get(
        "peaks",
        [],
    )
):

    if (
        peak.get("d_spacing")
        is None
        or
        peak.get("two_theta")
        is None
    ):
        continue

    implied.append(
        implied_wavelength(
            peak["d_spacing"],
            peak["two_theta"],
        )
    )

implied_median = median(
    implied
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
# Candidate analysis
# ============================================================

results = []


for candidate in candidates:

    calculated = (
        calculate_reflections(
            PROJECT_ROOT
            / candidate[
                "file_path"
            ],
            wavelength,
            raw_min,
            raw_max,
        )
    )

    top_theoretical = sorted(
        calculated[
            "reflections"
        ],
        key=lambda item:
            item[
                "relative_intensity"
            ],
        reverse=True,
    )[:TOP_THEORETICAL]

    summary = summarize(
        top_theoretical,
        experimental_peaks,
    )

    results.append(
        {
            "source_id":
                candidate[
                    "source_id"
                ],

            "structure":
                calculated[
                    "structure"
                ],

            "theoretical":
                top_theoretical,

            "summary":
                summary,
        }
    )


# ============================================================
# Report
# ============================================================

print()
print("=" * 112)
print(
    "BUSTAMITE ONE-TO-ONE + ZERO-SHIFT PILOT"
)
print("=" * 112)

print(
    "sample_id:                     ",
    SAMPLE_ID,
)

print(
    "measurement_id:                ",
    measurement_id,
)

print(
    "radiation class:               ",
    radiation_class,
)

print(
    "validation wavelength:         ",
    f"{wavelength:.6f}",
)

print(
    "Bragg implied wavelength:      ",
    f"{implied_median:.6f}",
)

print(
    "experimental peaks detected:   ",
    len(experimental_peaks),
)

print(
    "theoretical peaks per CIF:     ",
    TOP_THEORETICAL,
)

print(
    "initial zero-shift window:     ",
    f"+/- {INITIAL_WINDOW:.2f} deg",
)

print(
    "final matching window:         ",
    f"+/- {FINAL_WINDOW:.2f} deg",
)


print()
print("-" * 112)
print(
    "ZERO-SHIFT-CORRECTED AGREEMENT"
)
print("-" * 112)

print(
    f"{'COD':<12}"
    f"{'Zero shift':>13}"
    f"{'Matched':>10}"
    f"{'Median resid':>15}"
    f"{'Mean resid':>13}"
    f"{'Weighted':>13}"
    f"{'Max resid':>12}"
    f"{'Slope':>12}"
)


for item in results:

    summary = item[
        "summary"
    ]

    slope = summary.get(
        "residual_slope"
    )

    print(
        f"{item['source_id']:<12}"
        f"{summary['zero_shift']:>13.5f}"
        f"{summary['matched_count']:>10d}"
        f"{summary.get('median_abs_residual', float('nan')):>15.5f}"
        f"{summary.get('mean_abs_residual', float('nan')):>13.5f}"
        f"{summary.get('weighted_mean_abs_residual', float('nan')):>13.5f}"
        f"{summary.get('max_abs_residual', float('nan')):>12.5f}"
        f"{slope if slope is not None else float('nan'):>12.6f}"
    )


print()
print(
    f"{'COD':<12}"
    f"{'<=0.03':>12}"
    f"{'<=0.05':>12}"
    f"{'<=0.10':>12}"
)


for item in results:

    summary = item[
        "summary"
    ]

    print(
        f"{item['source_id']:<12}"
        f"{summary.get('within_0_03', 0):>12d}"
        f"{summary.get('within_0_05', 0):>12d}"
        f"{summary.get('within_0_10', 0):>12d}"
    )


# ============================================================
# Detailed one-to-one matches
# ============================================================

for item in results:

    print()
    print("=" * 112)

    print(
        f"COD {item['source_id']} "
        "ONE-TO-ONE MATCHES"
    )

    print("=" * 112)

    print(
        f"{'hkl':<16}"
        f"{'Calc':>11}"
        f"{'Corrected':>12}"
        f"{'Observed':>12}"
        f"{'Residual':>12}"
        f"{'Icalc':>10}"
        f"{'Iobs':>10}"
    )

    summary = item[
        "summary"
    ]

    shift = summary[
        "zero_shift"
    ]

    matches = sorted(
        summary[
            "matches"
        ],
        key=lambda match:
            match[
                "theoretical"
            ][
                "two_theta"
            ],
    )

    for match in matches:

        theory = match[
            "theoretical"
        ]

        experimental = match[
            "experimental"
        ]

        print(
            f"{str(theory['hkl']):<16}"
            f"{theory['two_theta']:>11.4f}"
            f"{theory['two_theta'] + shift:>12.4f}"
            f"{experimental['two_theta']:>12.4f}"
            f"{match['residual']:>12.4f}"
            f"{theory['relative_intensity']:>10.2f}"
            f"{experimental['intensity']:>10.2f}"
        )


print()
print("=" * 112)
print(
    "No candidate is automatically selected."
)
print(
    "The pilot separates a constant 2theta "
    "offset from residual structural mismatch."
)
print("=" * 112)

