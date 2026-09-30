from pathlib import Path
from math import asin, degrees
from html import escape

from crystaldb.mongo import get_database


PROJECT_ROOT = Path(__file__).resolve().parents[1]

OUTPUT_DIR = (
    PROJECT_ROOT
    / "reports"
    / "figures"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


MO_WAVELENGTH = 0.71073

# Diagnostic only.
# NOT a final scientific threshold.
SUPPORT_WINDOW_DEG = 0.20


db = get_database(
    database_name="rruff"
)


def normalize_profile(intensities):
    values = [
        float(value)
        for value in intensities
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


def normalize_stick_intensities(peaks):
    values = [
        max(
            float(
                peak.get(
                    "intensity",
                    0.0,
                )
            ),
            0.0,
        )
        for peak in peaks
    ]

    maximum = max(
        values,
        default=0.0,
    )

    if maximum <= 0:
        return [
            0.0
            for _ in values
        ]

    return [
        value / maximum * 100.0
        for value in values
    ]


def recalculate_two_theta(
    d_spacing,
    wavelength,
):
    d_spacing = float(
        d_spacing
    )

    argument = (
        wavelength
        / (2.0 * d_spacing)
    )

    if (
        argument <= 0
        or argument > 1
    ):
        return None

    theta = asin(
        argument
    )

    return (
        2.0
        * degrees(theta)
    )


def build_original_peaks(
    dif_peaks,
):
    output = []

    for peak in dif_peaks:

        two_theta = peak.get(
            "two_theta"
        )

        if two_theta is None:
            continue

        output.append(
            {
                **peak,
                "plot_two_theta":
                    float(two_theta),
            }
        )

    return output


def build_recalculated_peaks(
    dif_peaks,
    wavelength,
):
    output = []

    for peak in dif_peaks:

        d_spacing = peak.get(
            "d_spacing"
        )

        if d_spacing is None:
            continue

        two_theta = (
            recalculate_two_theta(
                d_spacing,
                wavelength,
            )
        )

        if two_theta is None:
            continue

        output.append(
            {
                **peak,
                "plot_two_theta":
                    two_theta,
            }
        )

    return output


def support_score(
    raw_two_theta,
    raw_normalized,
    theoretical_peaks,
):
    weighted_signal = 0.0
    total_weight = 0.0

    for peak in theoretical_peaks:

        position = peak[
            "plot_two_theta"
        ]

        weight = max(
            float(
                peak.get(
                    "intensity",
                    0.0,
                )
            ),
            0.0,
        )

        if weight <= 0:
            continue

        local_max = None

        for angle, intensity in zip(
            raw_two_theta,
            raw_normalized,
        ):
            if abs(
                float(angle)
                - position
            ) <= SUPPORT_WINDOW_DEG:

                if (
                    local_max is None
                    or intensity > local_max
                ):
                    local_max = intensity

        if local_max is None:
            continue

        weighted_signal += (
            weight
            * (
                local_max
                / 100.0
            )
        )

        total_weight += weight

    if total_weight <= 0:
        return None

    return (
        weighted_signal
        / total_weight
    )


def write_svg_plot(
    sample_id,
    mode_name,
    title_suffix,
    theoretical_peaks,
):
    raw = db.xy_raw.find_one(
        {
            "sample_id":
                sample_id
        }
    )

    if raw is None:
        raise RuntimeError(
            f"Missing XY_RAW: "
            f"{sample_id}"
        )

    xrd = raw.get(
        "xrd",
        {},
    )

    two_theta = (
        xrd.get(
            "two_theta"
        )
        or []
    )

    intensity = (
        xrd.get(
            "intensity"
        )
        or []
    )

    if (
        not two_theta
        or not intensity
    ):
        raise RuntimeError(
            f"Missing XY data: "
            f"{sample_id}"
        )

    normalized_raw = (
        normalize_profile(
            intensity
        )
    )

    raw_min = float(
        two_theta[0]
    )

    raw_max = float(
        two_theta[-1]
    )

    visible_peaks = [
        peak
        for peak in theoretical_peaks
        if (
            raw_min
            <= peak[
                "plot_two_theta"
            ]
            <= raw_max
        )
    ]

    stick_heights = (
        normalize_stick_intensities(
            visible_peaks
        )
    )

    score = support_score(
        two_theta,
        normalized_raw,
        visible_peaks,
    )


    # ====================================================
    # SVG geometry
    # ====================================================

    width = 1200
    height = 520

    left = 90
    right = 40
    top = 85
    bottom = 75

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


    def map_x(value):
        return (
            left
            + (
                float(value)
                - raw_min
            )
            / (
                raw_max
                - raw_min
            )
            * plot_width
        )


    def map_y(value):
        return (
            top
            + plot_height
            - (
                float(value)
                / 100.0
            )
            * plot_height
        )


    # Keep SVG compact while preserving
    # the visual profile.
    max_plot_points = 3500

    step = max(
        1,
        len(two_theta)
        // max_plot_points,
    )

    profile_points = []

    for index in range(
        0,
        len(two_theta),
        step,
    ):
        profile_points.append(
            (
                map_x(
                    two_theta[index]
                ),
                map_y(
                    normalized_raw[index]
                ),
            )
        )

    polyline = " ".join(
        f"{x:.2f},{y:.2f}"
        for x, y
        in profile_points
    )


    mineral = (
        raw.get("mineral")
        or sample_id
    )

    title = (
        f"{sample_id} | "
        f"{mineral} | "
        f"{title_suffix}"
    )


    svg = []

    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" '
        f'height="{height}" '
        f'viewBox="0 0 {width} {height}">'
    )

    svg.append(
        '<rect width="100%" height="100%" '
        'fill="white"/>'
    )

    svg.append(
        '<style>'
        'text {font-family: Arial, Helvetica, sans-serif;}'
        '</style>'
    )


    # Title
    svg.append(
        f'<text x="{left}" y="38" '
        f'font-size="22" '
        f'font-weight="bold" '
        f'fill="#222">'
        f'{escape(title)}'
        f'</text>'
    )


    # Horizontal grid + y labels
    for value in [
        0,
        25,
        50,
        75,
        100,
    ]:
        y = map_y(
            value
        )

        svg.append(
            f'<line '
            f'x1="{left}" '
            f'x2="{left + plot_width}" '
            f'y1="{y:.2f}" '
            f'y2="{y:.2f}" '
            f'stroke="#dddddd" '
            f'stroke-width="1"/>'
        )

        svg.append(
            f'<text '
            f'x="{left - 12}" '
            f'y="{y + 4:.2f}" '
            f'text-anchor="end" '
            f'font-size="12" '
            f'fill="#555">'
            f'{value}'
            f'</text>'
        )


    # X axis ticks
    tick_count = 8

    for index in range(
        tick_count + 1
    ):
        value = (
            raw_min
            + (
                raw_max
                - raw_min
            )
            * index
            / tick_count
        )

        x = map_x(
            value
        )

        svg.append(
            f'<line '
            f'x1="{x:.2f}" '
            f'x2="{x:.2f}" '
            f'y1="{top + plot_height}" '
            f'y2="{top + plot_height + 6}" '
            f'stroke="#444"/>'
        )

        svg.append(
            f'<text '
            f'x="{x:.2f}" '
            f'y="{top + plot_height + 24}" '
            f'text-anchor="middle" '
            f'font-size="12" '
            f'fill="#555">'
            f'{value:.1f}'
            f'</text>'
        )


    # Axes
    svg.append(
        f'<line '
        f'x1="{left}" '
        f'x2="{left}" '
        f'y1="{top}" '
        f'y2="{top + plot_height}" '
        f'stroke="#333" '
        f'stroke-width="1.4"/>'
    )

    svg.append(
        f'<line '
        f'x1="{left}" '
        f'x2="{left + plot_width}" '
        f'y1="{top + plot_height}" '
        f'y2="{top + plot_height}" '
        f'stroke="#333" '
        f'stroke-width="1.4"/>'
    )


    # Experimental profile
    svg.append(
        f'<polyline '
        f'points="{polyline}" '
        f'fill="none" '
        f'stroke="#222222" '
        f'stroke-width="1.3"/>'
    )


    # DIF sticks
    for peak, height_value in zip(
        visible_peaks,
        stick_heights,
    ):
        x = map_x(
            peak[
                "plot_two_theta"
            ]
        )

        y_top = map_y(
            height_value
        )

        y_bottom = map_y(
            0
        )

        svg.append(
            f'<line '
            f'x1="{x:.2f}" '
            f'x2="{x:.2f}" '
            f'y1="{y_bottom:.2f}" '
            f'y2="{y_top:.2f}" '
            f'stroke="#2878B5" '
            f'stroke-width="1" '
            f'opacity="0.75"/>'
        )


    # Axis labels
    svg.append(
        f'<text '
        f'x="{left + plot_width / 2:.2f}" '
        f'y="{height - 20}" '
        f'text-anchor="middle" '
        f'font-size="15" '
        f'fill="#333">'
        f'2θ (degrees)'
        f'</text>'
    )

    svg.append(
        f'<text '
        f'x="22" '
        f'y="{top + plot_height / 2:.2f}" '
        f'text-anchor="middle" '
        f'font-size="15" '
        f'fill="#333" '
        f'transform="rotate(-90 22 '
        f'{top + plot_height / 2:.2f})">'
        f'Normalized intensity'
        f'</text>'
    )


    # Legend
    legend_y = 62

    svg.append(
        f'<line '
        f'x1="{left}" '
        f'x2="{left + 32}" '
        f'y1="{legend_y}" '
        f'y2="{legend_y}" '
        f'stroke="#222222" '
        f'stroke-width="2"/>'
    )

    svg.append(
        f'<text '
        f'x="{left + 40}" '
        f'y="{legend_y + 5}" '
        f'font-size="13" '
        f'fill="#333">'
        f'RRUFF experimental XY_RAW'
        f'</text>'
    )

    second_x = left + 250

    svg.append(
        f'<line '
        f'x1="{second_x}" '
        f'x2="{second_x + 32}" '
        f'y1="{legend_y}" '
        f'y2="{legend_y}" '
        f'stroke="#2878B5" '
        f'stroke-width="3"/>'
    )

    svg.append(
        f'<text '
        f'x="{second_x + 40}" '
        f'y="{legend_y + 5}" '
        f'font-size="13" '
        f'fill="#333">'
        f'DIF calculated peak positions'
        f'</text>'
    )


    svg.append(
        '</svg>'
    )


    output_file = (
        OUTPUT_DIR
        / (
            f"{sample_id}_"
            f"{mode_name}.svg"
        )
    )

    output_file.write_text(
        "\n".join(svg),
        encoding="utf-8",
    )


    return {
        "sample_id":
            sample_id,

        "mode":
            mode_name,

        "visible_peak_count":
            len(
                visible_peaks
            ),

        "support_score":
            score,

        "output_file":
            output_file,
    }


def load_dif_peaks(
    sample_id,
):
    dif = db.dif.find_one(
        {
            "sample_id":
                sample_id
        }
    )

    if dif is None:
        raise RuntimeError(
            f"Missing DIF: "
            f"{sample_id}"
        )

    diffraction = dif.get(
        "diffraction",
        {},
    )

    peaks = (
        diffraction.get(
            "peaks"
        )
        or []
    )

    wavelength = (
        diffraction.get(
            "x_ray_wavelength"
        )
    )

    return (
        peaks,
        wavelength,
    )


def main():

    results = []


    # ====================================================
    # Positive control
    # ====================================================

    sample_id = "R060524"

    peaks, wavelength = (
        load_dif_peaks(
            sample_id
        )
    )

    results.append(
        write_svg_plot(
            sample_id=
                sample_id,

            mode_name=
                "dif_original",

            title_suffix=
                (
                    "DIF original "
                    f"lambda={wavelength}"
                ),

            theoretical_peaks=
                build_original_peaks(
                    peaks
                ),
        )
    )


    # ====================================================
    # Mo-labelled record with Cu-like DIF wavelength
    # ====================================================

    sample_id = "R060226"

    peaks, wavelength = (
        load_dif_peaks(
            sample_id
        )
    )

    results.append(
        write_svg_plot(
            sample_id=
                sample_id,

            mode_name=
                "dif_original",

            title_suffix=
                (
                    "DIF original "
                    f"lambda={wavelength}"
                ),

            theoretical_peaks=
                build_original_peaks(
                    peaks
                ),
        )
    )


    results.append(
        write_svg_plot(
            sample_id=
                sample_id,

            mode_name=
                "dif_recalculated_mo",

            title_suffix=
                (
                    "DIF d-spacing "
                    "recalculated with "
                    f"lambda={MO_WAVELENGTH}"
                ),

            theoretical_peaks=
                build_recalculated_peaks(
                    peaks,
                    MO_WAVELENGTH,
                ),
        )
    )


    print()
    print("=" * 72)
    print(
        "MO-WAVELENGTH DIFFRACTION "
        "VALIDATION"
    )
    print("=" * 72)

    print(
        "Diagnostic window:",
        f"+/- {SUPPORT_WINDOW_DEG:.2f} deg",
    )

    for result in results:

        score = result[
            "support_score"
        ]

        if score is None:
            score_text = "N/A"
        else:
            score_text = (
                f"{score:.4f}"
            )

        print()
        print(
            result["sample_id"],
            result["mode"],
        )

        print(
            "  theoretical peaks in range:",
            result[
                "visible_peak_count"
            ],
        )

        print(
            "  diagnostic support score:",
            score_text,
        )

        print(
            "  figure:",
            result[
                "output_file"
            ],
        )

    print()
    print("=" * 72)

    print(
        "NOTE: support score is "
        "diagnostic only."
    )

    print("=" * 72)


if __name__ == "__main__":
    main()
