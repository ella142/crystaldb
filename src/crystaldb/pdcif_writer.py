from pathlib import Path


def write_pdcif(
    output_path,
    measurement_id,
    mineral_name,
    two_theta,
    raw_intensity,
    processed_intensity,
    wavelength=None,
):
    output_path = Path(output_path)

    if not (
        len(two_theta)
        == len(raw_intensity)
        == len(processed_intensity)
    ):
        raise ValueError(
            "two_theta, raw_intensity and processed_intensity "
            "must have the same length"
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    lines = [
        "# crystaldb canonical powder diffraction file",
        "#",
        f"data_{measurement_id}",
        "",
        f"_pd_block_id '{measurement_id}'",
        f"_chemical_name_mineral '{mineral_name}'",
    ]

    if wavelength is not None:
        lines.append(
            f"_diffrn_radiation_wavelength {wavelength}"
        )

    lines.extend(
        [
            "",
            "loop_",
            "_pd_meas_2theta_scan",
            "_pd_meas_intensity_total",
            "_pd_proc_intensity_total",
        ]
    )

    for x, raw, processed in zip(
        two_theta,
        raw_intensity,
        processed_intensity,
    ):
        lines.append(
            f"{x:.6f} {raw:.8g} {processed:.8g}"
        )

    output_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    return output_path