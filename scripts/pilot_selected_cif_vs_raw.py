import json
from math import (
    asin,
    cos,
    degrees,
    radians,
    sin,
)
from pathlib import Path

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

VALIDATION_WAVELENGTH = 1.541838

# Diagnostic search window only.
# Not a final matching threshold.
SEARCH_WINDOW = 0.30


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

    return len(
        equivalents
    )


def lorentz_polarization(
    two_theta,
):
    """
    Approximate unpolarized
    Bragg-Brentano LP factor.

    Used only for pilot powder-intensity
    visualization.
    """

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


def normalize(values):
    values = [
        float(value)
        for value in values
    ]

    if not values:
        return []

    minimum = min(values)

    shifted = [
        value - minimum
        for value in values
    ]

    maximum = max(
        shifted
    )

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


# ============================================================
# Load frozen v1 resolution
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

selected = (
    resolution[
        "selected_candidate"
    ]
)


# ============================================================
# Experimental profile
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

xrd = raw["xrd"]

raw_x = [
    float(value)
    for value
    in xrd["two_theta"]
]

raw_y = normalize(
    xrd["intensity"]
)

raw_min = raw_x[0]
raw_max = raw_x[-1]


# ============================================================
# Selected CIF
# ============================================================

cif_path = (
    PROJECT_ROOT
    / selected["file_path"]
)

document = gemmi.cif.read_file(
    str(cif_path)
)

block = document.sole_block()

structure = (
    gemmi.make_small_structure_from_block(
        block
    )
)

spacegroup = (
    structure.spacegroup
)

if spacegroup is None:

    structure.determine_and_set_spacegroup()

    spacegroup = (
        structure.spacegroup
    )


# ============================================================
# Reflection range
# ============================================================

theta_max = radians(
    raw_max / 2.0
)

theta_min = radians(
    raw_min / 2.0
)

d_min = (
    VALIDATION_WAVELENGTH
    / (
        2.0
        * sin(theta_max)
    )
)

d_max = (
    VALIDATION_WAVELENGTH
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
            VALIDATION_WAVELENGTH,
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

    powder_intensity = (
        f_squared
        * mult
        * lp
    )

    reflections.append(
        {
            "hkl": hkl,
            "two_theta":
                two_theta,
            "d_spacing":
                d_spacing,
            "intensity":
                powder_intensity,
        }
    )


# ============================================================
# Normalize theoretical sticks
# ============================================================

max_theoretical = max(
    item["intensity"]
    for item in reflections
)

for item in reflections:

    item["relative_intensity"] = (
        item["intensity"]
        / max_theoretical
        * 100.0
    )


# ============================================================
# Experimental support near theoretical peaks
# ============================================================

for item in reflections:

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

        item[
            "observed_two_theta"
        ] = None

        item[
            "observed_intensity"
        ] = None

        item[
            "delta_two_theta"
        ] = None

        continue

    observed_angle, observed_intensity = max(
        local,
        key=lambda pair:
            pair[1],
    )

    item[
        "observed_two_theta"
    ] = observed_angle

    item[
        "observed_intensity"
    ] = observed_intensity

    item[
        "delta_two_theta"
    ] = (
        observed_angle
        - target
    )


# ============================================================
# Console table
# ============================================================

strongest = sorted(
    reflections,
    key=lambda item:
        item[
            "relative_intensity"
        ],
    reverse=True,
)


print()
print("=" * 92)
print(
    "SELECTED CIF vs EXPERIMENTAL RAW PILOT"
)
print("=" * 92)

print(
    "sample_id:              ",
    SAMPLE_ID,
)

print(
    "mineral:                ",
    record.get("mineral"),
)

print(
    "selected COD:           ",
    selected.get("source_id"),
)

print(
    "wavelength:             ",
    VALIDATION_WAVELENGTH,
)

print(
    "search window:          ",
    f"+/- {SEARCH_WINDOW:.2f} deg",
)

print(
    "reflection families:    ",
    len(reflections),
)


print()
print(
    f"{'Rank':<6}"
    f"{'hkl':<16}"
    f"{'Calc 2theta':>13}"
    f"{'Icalc':>10}"
    f"{'Obs 2theta':>13}"
    f"{'Iobs':>10}"
    f"{'Delta':>10}"
)


for rank, item in enumerate(
    strongest[:15],
    start=1,
):

    observed = item[
        "observed_two_theta"
    ]

    observed_intensity = item[
        "observed_intensity"
    ]

    delta = item[
        "delta_two_theta"
    ]

    print(
        f"{rank:<6}"
        f"{str(item['hkl']):<16}"
        f"{item['two_theta']:>13.4f}"
        f"{item['relative_intensity']:>10.2f}"
        f"{observed if observed is not None else float('nan'):>13.4f}"
        f"{observed_intensity if observed_intensity is not None else float('nan'):>10.2f}"
        f"{delta if delta is not None else float('nan'):>10.4f}"
    )


# ============================================================
# SVG
# ============================================================

width = 1250
height = 560

left = 90
right = 40
top = 90
bottom = 80

plot_width = (
    width
    - left
    - right
)

plot_height = (
    height
    - top
    - bottom
)


def sx(value):

    return (
        left
        + (
            value - raw_min
        )
        / (
            raw_max - raw_min
        )
        * plot_width
    )


def sy(value):

    return (
        top
        + plot_height
        - value
        / 100.0
        * plot_height
    )


max_points = 4000

step = max(
    1,
    len(raw_x)
    // max_points,
)

profile_points = " ".join(
    (
        f"{sx(raw_x[i]):.2f},"
        f"{sy(raw_y[i]):.2f}"
    )
    for i in range(
        0,
        len(raw_x),
        step,
    )
)


svg = []

svg.append(
    f'<svg xmlns="http://www.w3.org/2000/svg" '
    f'width="{width}" '
    f'height="{height}" '
    f'viewBox="0 0 {width} {height}">'
)

svg.append(
    '<rect width="100%" height="100%" fill="white"/>'
)

svg.append(
    '<style>'
    'text{font-family:Arial,Helvetica,sans-serif;}'
    '</style>'
)


svg.append(
    f'<text x="{left}" y="38" '
    f'font-size="24" '
    f'font-weight="bold">'
    f'R040017 Cassiterite: selected CIF vs experimental PXRD'
    f'</text>'
)

svg.append(
    f'<text x="{left}" y="66" '
    f'font-size="14" fill="#555">'
    f'COD 9007533 | Cu-like lambda = {VALIDATION_WAVELENGTH:.6f} A'
    f'</text>'
)


# Grid
for value in [
    0,
    25,
    50,
    75,
    100,
]:

    y = sy(value)

    svg.append(
        f'<line x1="{left}" '
        f'x2="{left + plot_width}" '
        f'y1="{y:.2f}" '
        f'y2="{y:.2f}" '
        f'stroke="#dddddd"/>'
    )


# Experimental curve
svg.append(
    f'<polyline '
    f'points="{profile_points}" '
    f'fill="none" '
    f'stroke="#222222" '
    f'stroke-width="1.4"/>'
)


# Theoretical sticks
for item in reflections:

    x = sx(
        item["two_theta"]
    )

    y0 = sy(0)

    y1 = sy(
        item[
            "relative_intensity"
        ]
    )

    svg.append(
        f'<line '
        f'x1="{x:.2f}" '
        f'x2="{x:.2f}" '
        f'y1="{y0:.2f}" '
        f'y2="{y1:.2f}" '
        f'stroke="#2878B5" '
        f'stroke-width="1.5" '
        f'opacity="0.80"/>'
    )


# Axes
svg.append(
    f'<line '
    f'x1="{left}" '
    f'x2="{left}" '
    f'y1="{top}" '
    f'y2="{top + plot_height}" '
    f'stroke="#333"/>'
)

svg.append(
    f'<line '
    f'x1="{left}" '
    f'x2="{left + plot_width}" '
    f'y1="{top + plot_height}" '
    f'y2="{top + plot_height}" '
    f'stroke="#333"/>'
)


# X ticks
for index in range(10):

    value = (
        raw_min
        + (
            raw_max - raw_min
        )
        * index
        / 9
    )

    x = sx(value)

    svg.append(
        f'<text '
        f'x="{x:.2f}" '
        f'y="{top + plot_height + 25}" '
        f'text-anchor="middle" '
        f'font-size="12">'
        f'{value:.1f}'
        f'</text>'
    )


svg.append(
    f'<text '
    f'x="{left + plot_width / 2}" '
    f'y="{height - 22}" '
    f'text-anchor="middle" '
    f'font-size="15">'
    f'2theta (degrees)'
    f'</text>'
)

svg.append(
    f'<text '
    f'x="24" '
    f'y="{top + plot_height / 2}" '
    f'text-anchor="middle" '
    f'font-size="15" '
    f'transform="rotate(-90 24 '
    f'{top + plot_height / 2})">'
    f'Normalized intensity'
    f'</text>'
)


# Legend
svg.append(
    f'<line x1="{left}" '
    f'x2="{left + 35}" '
    f'y1="78" y2="78" '
    f'stroke="#222" '
    f'stroke-width="2"/>'
)

svg.append(
    f'<text x="{left + 43}" '
    f'y="83" font-size="13">'
    f'RRUFF experimental XY_RAW'
    f'</text>'
)

svg.append(
    f'<line x1="{left + 260}" '
    f'x2="{left + 295}" '
    f'y1="78" y2="78" '
    f'stroke="#2878B5" '
    f'stroke-width="3"/>'
)

svg.append(
    f'<text x="{left + 303}" '
    f'y="83" font-size="13">'
    f'Selected CIF theoretical reflections'
    f'</text>'
)


svg.append(
    '</svg>'
)


output_file = (
    OUTPUT_DIR
    / "R040017_selected_cif_vs_raw.svg"
)

output_file.write_text(
    "\n".join(svg),
    encoding="utf-8",
)


print()
print(
    "Figure:",
    output_file,
)

print()
print("=" * 92)
print(
    "PILOT COMPLETE"
)
print("=" * 92)

