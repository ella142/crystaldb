import json
from collections import defaultdict
from pathlib import Path
from statistics import median


PROJECT_ROOT = Path(__file__).resolve().parents[1]

CONTRAST_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_candidate_contrast_calibration_v1.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "mappings"
    / "rruff_blind_bibliography_recovery_v1.json"
)


# ============================================================
# Load
# ============================================================

data = json.loads(
    CONTRAST_FILE.read_text(
        encoding="utf-8"
    )
)

record_results = (
    data[
        "record_results"
    ]
)

pair_results = (
    data[
        "pair_results"
    ]
)


# ============================================================
# Helpers
# ============================================================

def percentile(
    values,
    q,
):
    values = sorted(
        float(value)
        for value in values
    )

    if not values:
        return None

    if len(values) == 1:
        return values[0]

    position = (
        (len(values) - 1)
        * q
    )

    lower = int(
        position
    )

    upper = min(
        lower + 1,
        len(values) - 1,
    )

    fraction = (
        position - lower
    )

    return (
        values[lower]
        * (
            1.0 - fraction
        )
        +
        values[upper]
        * fraction
    )


def separation_bin(
    value,
):
    if value is None:
        return "missing"

    if value <= 0.02:
        return "le_0.02"

    if value <= 0.05:
        return "0.02_to_0.05"

    if value <= 0.10:
        return "0.05_to_0.10"

    return "gt_0.10"


# ============================================================
# Index pair comparisons by sample
# ============================================================

pairs_by_sample = defaultdict(
    list
)

for pair in pair_results:

    pairs_by_sample[
        pair[
            "sample_id"
        ]
    ].append(
        pair
    )


# ============================================================
# Blind diffraction recovery
# ============================================================

results = []


for record in record_results:

    sample_id = (
        record[
            "sample_id"
        ]
    )

    selected_source_id = str(
        record[
            "selected_source_id"
        ]
    )

    sample_pairs = (
        pairs_by_sample[
            sample_id
        ]
    )


    # --------------------------------------------------------
    # Rebuild all evaluable candidates.
    #
    # Bibliography-selected CIF is included only as another
    # candidate here. We do NOT give it any preference.
    # --------------------------------------------------------

    candidates = {
        selected_source_id: {
            "source_id":
                selected_source_id,

            "metrics":
                record[
                    "selected_metrics"
                ],

            "role":
                "hidden_bibliographic_reference",
        }
    }


    for pair in sample_pairs:

        alternative_id = str(
            pair[
                "alternative_source_id"
            ]
        )

        candidates[
            alternative_id
        ] = {
            "source_id":
                alternative_id,

            "metrics":
                pair[
                    "alternative_metrics"
                ],

            "role":
                "alternative",
        }


    valid_candidates = [
        candidate
        for candidate
        in candidates.values()

        if candidate[
            "metrics"
        ].get(
            "weighted_mean_abs_residual"
        )
        is not None
    ]


    valid_candidates.sort(
        key=lambda candidate:
            candidate[
                "metrics"
            ][
                "weighted_mean_abs_residual"
            ]
    )


    if not valid_candidates:
        continue


    blind_best = (
        valid_candidates[0]
    )

    blind_runner = (
        valid_candidates[1]
        if len(
            valid_candidates
        ) >= 2
        else None
    )


    blind_best_id = (
        blind_best[
            "source_id"
        ]
    )


    # --------------------------------------------------------
    # Blind residual advantage
    # --------------------------------------------------------

    blind_residual_gap = None

    if blind_runner is not None:

        blind_residual_gap = (
            blind_runner[
                "metrics"
            ][
                "weighted_mean_abs_residual"
            ]
            -
            blind_best[
                "metrics"
            ][
                "weighted_mean_abs_residual"
            ]
        )


    # --------------------------------------------------------
    # Bibliography agreement
    # --------------------------------------------------------

    recovered = (
        blind_best_id
        == selected_source_id
    )


    # --------------------------------------------------------
    # Separation between bibliography-selected CIF and
    # blind diffraction-best CIF.
    #
    # For disagreements, this directly tells us whether
    # diffraction chose a record that is theoretically
    # distinguishable from the provenance-selected record.
    #
    # For agreements, selected == blind best, so instead
    # record the nearest theoretical competitor among
    # selected-vs-alternative comparisons.
    # --------------------------------------------------------

    selected_vs_blind_separation = None
    nearest_competitor_separation = None


    if recovered:

        separations = [
            pair[
                "theoretical_separation"
            ][
                "median_nearest_difference"
            ]

            for pair in sample_pairs

            if pair.get(
                "theoretical_separation"
            )
        ]

        if separations:

            nearest_competitor_separation = min(
                separations
            )

    else:

        matching_pair = next(
            (
                pair
                for pair in sample_pairs

                if str(
                    pair[
                        "alternative_source_id"
                    ]
                )
                == blind_best_id
            ),
            None,
        )

        if matching_pair is not None:

            selected_vs_blind_separation = (
                matching_pair[
                    "theoretical_separation"
                ][
                    "median_nearest_difference"
                ]
            )


    # --------------------------------------------------------
    # Selected position in blind ranking
    # --------------------------------------------------------

    selected_rank = next(
        (
            index
            for index, candidate
            in enumerate(
                valid_candidates,
                start=1,
            )

            if candidate[
                "source_id"
            ]
            == selected_source_id
        ),
        None,
    )


    results.append(
        {
            "sample_id":
                sample_id,

            "mineral":
                record.get(
                    "mineral"
                ),

            "radiation_class":
                record.get(
                    "radiation",
                    {},
                ).get(
                    "radiation_class"
                ),

            "bibliography_selected_source_id":
                selected_source_id,

            "blind_diffraction_best_source_id":
                blind_best_id,

            "blind_runner_up_source_id":
                (
                    blind_runner[
                        "source_id"
                    ]
                    if blind_runner
                    else None
                ),

            "bibliography_recovered":
                recovered,

            "bibliography_selected_rank":
                selected_rank,

            "candidate_count":
                len(
                    valid_candidates
                ),

            "blind_best_metrics":
                blind_best[
                    "metrics"
                ],

            "blind_residual_gap":
                blind_residual_gap,

            "selected_vs_blind_separation":
                selected_vs_blind_separation,

            "selected_vs_blind_separation_bin":
                separation_bin(
                    selected_vs_blind_separation
                ),

            "nearest_competitor_separation_when_recovered":
                nearest_competitor_separation,

            "nearest_competitor_separation_bin_when_recovered":
                separation_bin(
                    nearest_competitor_separation
                ),

            "all_alternatives_evaluable":
                record[
                    "all_alternatives_evaluable"
                ],
        }
    )


# ============================================================
# Overall recovery
# ============================================================

recovered_records = [
    result
    for result in results

    if result[
        "bibliography_recovered"
    ]
]

disagreement_records = [
    result
    for result in results

    if not result[
        "bibliography_recovered"
    ]
]


print()
print("=" * 112)
print(
    "BLIND BIBLIOGRAPHY-RECOVERY CALIBRATION V1"
)
print("=" * 112)

print(
    "Records analysed:",
    len(
        results
    ),
)

print(
    "Blind diffraction best = bibliography-selected CIF:",
    len(
        recovered_records
    ),
    "/",
    len(
        results
    ),
    "=",
    f"{len(recovered_records) / len(results):.3f}",
)

print(
    "Blind diffraction best != bibliography-selected CIF:",
    len(
        disagreement_records
    ),
    "/",
    len(
        results
    ),
    "=",
    f"{len(disagreement_records) / len(results):.3f}",
)


# ============================================================
# Bibliography-selected rank distribution
# ============================================================

print()
print("=" * 112)
print(
    "BIBLIOGRAPHY-SELECTED CIF POSITION "
    "IN BLIND DIFFRACTION RANKING"
)
print("=" * 112)

for rank_limit in [
    1,
    2,
    3,
    5,
]:

    count = sum(
        result[
            "bibliography_selected_rank"
        ]
        is not None

        and

        result[
            "bibliography_selected_rank"
        ]
        <= rank_limit

        for result in results
    )

    print(
        f"rank <= {rank_limit:<2}: "
        f"{count:>4} / "
        f"{len(results)} "
        f"= "
        f"{count / len(results):.3f}"
    )


# ============================================================
# DISAGREEMENTS:
# how separable is blind best from bibliography-selected?
# ============================================================

print()
print("=" * 112)
print(
    "DISAGREEMENTS BY "
    "SELECTED-vs-BLIND-BEST THEORETICAL SEPARABILITY"
)
print("=" * 112)

print(
    "This asks whether a diffraction disagreement "
    "occurred between nearly indistinguishable "
    "or clearly separable CIF records."
)

print()

print(
    f"{'Stratum':<20}"
    f"{'Disagreements':>16}"
    f"{'Fraction':>14}"
    f"{'Median gap':>16}"
)


strata = [
    "le_0.02",
    "0.02_to_0.05",
    "0.05_to_0.10",
    "gt_0.10",
]


disagreement_strata = {}


for stratum in strata:

    subset = [
        result
        for result
        in disagreement_records

        if result[
            "selected_vs_blind_separation_bin"
        ]
        == stratum
    ]

    gaps = [
        result[
            "blind_residual_gap"
        ]

        for result in subset

        if result[
            "blind_residual_gap"
        ]
        is not None
    ]

    median_gap = (
        median(
            gaps
        )
        if gaps
        else None
    )

    disagreement_strata[
        stratum
    ] = {
        "count":
            len(
                subset
            ),

        "fraction_of_disagreements":
            (
                len(
                    subset
                )
                /
                len(
                    disagreement_records
                )

                if disagreement_records
                else 0.0
            ),

        "median_blind_residual_gap":
            median_gap,
    }

    print(
        f"{stratum:<20}"
        f"{len(subset):>16d}"
        f"{len(subset) / len(disagreement_records) if disagreement_records else 0:>14.3f}"
        f"{median_gap if median_gap is not None else float('nan'):>16.5f}"
    )


# ============================================================
# RECOVERED RECORDS:
# how close is the nearest competitor?
# ============================================================

print()
print("=" * 112)
print(
    "RECOVERED RECORDS BY "
    "NEAREST-COMPETITOR SEPARABILITY"
)
print("=" * 112)

print(
    "Even when bibliography is recovered, "
    "this indicates whether the winning record "
    "was intrinsically distinguishable."
)

print()

print(
    f"{'Stratum':<20}"
    f"{'Recovered':>14}"
    f"{'Fraction':>14}"
    f"{'Median gap':>16}"
)


recovered_strata = {}


for stratum in strata:

    subset = [
        result
        for result
        in recovered_records

        if result[
            "nearest_competitor_separation_bin_when_recovered"
        ]
        == stratum
    ]

    gaps = [
        result[
            "blind_residual_gap"
        ]

        for result in subset

        if result[
            "blind_residual_gap"
        ]
        is not None
    ]

    median_gap = (
        median(
            gaps
        )
        if gaps
        else None
    )

    recovered_strata[
        stratum
    ] = {
        "count":
            len(
                subset
            ),

        "fraction_of_recovered":
            (
                len(
                    subset
                )
                /
                len(
                    recovered_records
                )

                if recovered_records
                else 0.0
            ),

        "median_blind_residual_gap":
            median_gap,
    }

    print(
        f"{stratum:<20}"
        f"{len(subset):>14d}"
        f"{len(subset) / len(recovered_records) if recovered_records else 0:>14.3f}"
        f"{median_gap if median_gap is not None else float('nan'):>16.5f}"
    )


# ============================================================
# Separation distributions
# ============================================================

disagreement_separations = [
    result[
        "selected_vs_blind_separation"
    ]

    for result in disagreement_records

    if result[
        "selected_vs_blind_separation"
    ]
    is not None
]


recovered_nearest_separations = [
    result[
        "nearest_competitor_separation_when_recovered"
    ]

    for result in recovered_records

    if result[
        "nearest_competitor_separation_when_recovered"
    ]
    is not None
]


print()
print("=" * 112)
print(
    "SEPARABILITY DISTRIBUTION SUMMARY"
)
print("=" * 112)

print(
    f"{'Group':<38}"
    f"{'P50':>12}"
    f"{'P75':>12}"
    f"{'P90':>12}"
)


print(
    f"{'disagreement: selected vs blind best':<38}"
    f"{percentile(disagreement_separations, 0.50):>12.5f}"
    f"{percentile(disagreement_separations, 0.75):>12.5f}"
    f"{percentile(disagreement_separations, 0.90):>12.5f}"
)


print(
    f"{'recovered: nearest competitor':<38}"
    f"{percentile(recovered_nearest_separations, 0.50):>12.5f}"
    f"{percentile(recovered_nearest_separations, 0.75):>12.5f}"
    f"{percentile(recovered_nearest_separations, 0.90):>12.5f}"
)


# ============================================================
# Largest residual-gap disagreements
# ============================================================

largest_disagreements = sorted(
    disagreement_records,
    key=lambda result:
        (
            result[
                "blind_residual_gap"
            ]
            if result[
                "blind_residual_gap"
            ]
            is not None
            else -1
        ),
    reverse=True,
)


print()
print("=" * 112)
print(
    "15 STRONGEST BLIND-DIFFRACTION DISAGREEMENTS"
)
print("=" * 112)

print(
    f"{'sample':<12}"
    f"{'mineral':<24}"
    f"{'bibliography':<14}"
    f"{'blind best':<14}"
    f"{'rank':>7}"
    f"{'separation':>14}"
    f"{'gap':>12}"
)


for result in (
    largest_disagreements[:15]
):

    print(
        f"{result['sample_id']:<12}"
        f"{str(result.get('mineral'))[:22]:<24}"
        f"{result['bibliography_selected_source_id']:<14}"
        f"{result['blind_diffraction_best_source_id']:<14}"
        f"{result['bibliography_selected_rank']:>7}"
        f"{result['selected_vs_blind_separation'] if result['selected_vs_blind_separation'] is not None else float('nan'):>14.5f}"
        f"{result['blind_residual_gap'] if result['blind_residual_gap'] is not None else float('nan'):>12.5f}"
    )


# ============================================================
# Save
# ============================================================

output = {
    "version":
        "1.0",

    "purpose":
        (
            "Blind recovery audit comparing the "
            "lowest-weighted-residual CIF against "
            "an independently bibliography-selected "
            "CIF in 312 unique-bibliographic records."
        ),

    "important_note":
        (
            "Bibliography agreement is not treated "
            "as absolute ground truth or accuracy. "
            "This is an empirical provenance-recovery "
            "calibration for diffraction evidence."
        ),

    "input_file":
        (
            "data/mappings/"
            "rruff_candidate_contrast_calibration_v1.json"
        ),

    "counts": {
        "records":
            len(
                results
            ),

        "bibliography_recovered":
            len(
                recovered_records
            ),

        "bibliography_not_recovered":
            len(
                disagreement_records
            ),
    },

    "disagreement_strata":
        disagreement_strata,

    "recovered_strata":
        recovered_strata,

    "records":
        results,
}


OUTPUT_FILE.write_text(
    json.dumps(
        output,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print()
print(
    "Saved:",
    OUTPUT_FILE,
)

print()
print("=" * 112)
print(
    "BLIND BIBLIOGRAPHY-RECOVERY "
    "CALIBRATION V1 COMPLETE"
)
print("=" * 112)

