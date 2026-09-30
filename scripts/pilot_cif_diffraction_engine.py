import json
from math import asin, degrees, radians, sin
from pathlib import Path
from statistics import median

import gemmi

from crystaldb.mongo import get_database


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RESOLUTION_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_experimental_resolution_v1.json"
)

SAMPLE_ID = "R040017"

CU_WAVELENGTH = 1.541838
MO_WAVELENGTH = 0.710730


# ============================================================
# Helpers
# ============================================================

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


def reflection_multiplicity(
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


# ============================================================
# Load frozen experimental resolution
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

resolution = record[
    "structure_resolution"
]

selected = resolution.get(
    "selected_candidate"
)

if selected is None:
    raise RuntimeError(
        f"{SAMPLE_ID} has no "
        "selected CIF record."
    )


# ============================================================
# Load experimental RRUFF data
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

if raw is None:
    raise RuntimeError(
        "Missing XY_RAW"
    )

if dif is None:
    raise RuntimeError(
        "Missing DIF"
    )


two_theta_raw = (
    raw.get(
        "xrd",
        {},
    ).get(
        "two_theta"
    )
    or []
)

if not two_theta_raw:
    raise RuntimeError(
        "Missing RAW 2theta"
    )

raw_min = float(
    two_theta_raw[0]
)

raw_max = float(
    two_theta_raw[-1]
)


# ============================================================
# Derive radiation class from DIF peak geometry
# ============================================================

dif_peaks = (
    dif.get(
        "diffraction",
        {},
    ).get(
        "peaks"
    )
    or []
)

implied_values = []

for peak in dif_peaks:

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


if not implied_values:
    raise RuntimeError(
        "Cannot derive radiation "
        "class from DIF peaks."
    )

implied_median = median(
    implied_values
)

distance_to_cu = abs(
    implied_median
    - CU_WAVELENGTH
)

distance_to_mo = abs(
    implied_median
    - MO_WAVELENGTH
)

if distance_to_cu < distance_to_mo:

    radiation_class = "Cu-like"

    validation_wavelength = (
        CU_WAVELENGTH
    )

else:

    radiation_class = "Mo-like"

    validation_wavelength = (
        MO_WAVELENGTH
    )


# ============================================================
# Load selected CIF directly with Gemmi
# ============================================================

cif_path = (
    PROJECT_ROOT
    / selected["file_path"]
)

if not cif_path.exists():
    raise RuntimeError(
        f"CIF does not exist: "
        f"{cif_path}"
    )

cif_document = (
    gemmi.cif.read_file(
        str(cif_path)
    )
)

block = (
    cif_document.sole_block()
)

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

if spacegroup is None:
    raise RuntimeError(
        "Could not determine "
        "CIF space group."
    )


# ============================================================
# Experimental angular range -> d range
# ============================================================

theta_max = radians(
    raw_max / 2.0
)

theta_min = radians(
    raw_min / 2.0
)

d_min = (
    validation_wavelength
    / (
        2.0
        * sin(theta_max)
    )
)

d_max = (
    validation_wavelength
    / (
        2.0
        * sin(theta_min)
    )
)


# ============================================================
# Generate unique crystallographic reflections
# ============================================================

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
            validation_wavelength,
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

    structure_factor = (
        sf_calculator
        .calculate_sf_from_small_structure(
            structure,
            hkl,
        )
    )

    f_squared = (
        abs(
            structure_factor
        )
        ** 2
    )

    multiplicity = (
        reflection_multiplicity(
            spacegroup,
            hkl,
        )
    )

    approximate_intensity = (
        f_squared
        * multiplicity
    )

    reflections.append(
        {
            "hkl":
                hkl,

            "d_spacing":
                d_spacing,

            "two_theta":
                two_theta,

            "f_squared":
                f_squared,

            "multiplicity":
                multiplicity,

            "approximate_intensity":
                approximate_intensity,
        }
    )


# ============================================================
# Print audit
# ============================================================

print()
print("=" * 78)
print(
    "CIF DIFFRACTION ENGINE PILOT"
)
print("=" * 78)

print(
    "sample_id:                ",
    SAMPLE_ID,
)

print(
    "mineral:                  ",
    record.get("mineral"),
)

print(
    "measurement_id:           ",
    measurement_id,
)

print(
    "resolution_status:        ",
    resolution.get(
        "resolution_status"
    ),
)

print(
    "selected source:          ",
    selected.get("source"),
)

print(
    "selected source_id:       ",
    selected.get("source_id"),
)

print(
    "selected CIF:             ",
    selected.get("file_path"),
)

print()
print(
    "RAW 2theta range:         ",
    f"{raw_min:.4f}",
    "->",
    f"{raw_max:.4f}",
)

print(
    "Bragg-implied wavelength: ",
    f"{implied_median:.6f}",
)

print(
    "radiation class:          ",
    radiation_class,
)

print(
    "validation wavelength:    ",
    f"{validation_wavelength:.6f}",
)

print()
print(
    "CIF space group:          ",
    spacegroup.xhm(),
)

print(
    "CIF atom/site count:      ",
    len(
        structure.sites
    ),
)

print(
    "CIF cell:                 ",
    structure.cell,
)

print()
print(
    "d range used:             ",
    f"{d_min:.4f}",
    "->",
    f"{d_max:.4f}",
)

print(
    "generated reflections:    ",
    len(reflections),
)


# ============================================================
# Strongest theoretical reflections
# ============================================================

strongest = sorted(
    reflections,
    key=lambda item:
        item[
            "approximate_intensity"
        ],
    reverse=True,
)


maximum_intensity = max(
    (
        item[
            "approximate_intensity"
        ]
        for item
        in strongest
    ),
    default=0.0,
)


print()
print("=" * 78)
print(
    "20 STRONGEST CIF-DERIVED "
    "REFLECTIONS"
)
print("=" * 78)

print(
    f"{'Rank':<6}"
    f"{'hkl':<16}"
    f"{'2theta':>12}"
    f"{'d(A)':>12}"
    f"{'mult':>8}"
    f"{'Irel':>12}"
)


for rank, item in enumerate(
    strongest[:20],
    start=1,
):

    if maximum_intensity > 0:

        relative_intensity = (
            item[
                "approximate_intensity"
            ]
            / maximum_intensity
            * 100.0
        )

    else:

        relative_intensity = 0.0

    print(
        f"{rank:<6}"
        f"{str(item['hkl']):<16}"
        f"{item['two_theta']:>12.4f}"
        f"{item['d_spacing']:>12.4f}"
        f"{item['multiplicity']:>8d}"
        f"{relative_intensity:>12.2f}"
    )


print()
print("=" * 78)
print(
    "ENGINE TEST COMPLETE"
)
print("=" * 78)

