from pathlib import Path
import re
import requests


COD_SEARCH_URL = (
    "https://www.crystallography.net/cod/result"
)

COD_CIF_URL = (
    "https://www.crystallography.net/cod/{cod_id}.cif"
)


def search_cod_by_text(
    text,
    timeout=30,
):
    """
    Search COD broadly by text/mineral name.

    Returns a list of COD IDs.
    """

    response = requests.get(
        COD_SEARCH_URL,
        params={
            "text": text,
            "format": "lst",
        },
        timeout=timeout,
    )

    response.raise_for_status()

    cod_ids = []

    for line in response.text.splitlines():
        value = line.strip()

        if value.isdigit():
            cod_ids.append(value)

    return cod_ids


def download_cod_cif(
    cod_id,
    output_dir,
    timeout=30,
    overwrite=False,
):
    """
    Download one COD CIF file.

    Returns the saved Path.
    """

    output_dir = Path(output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        output_dir
        / f"{cod_id}.cif"
    )

    if (
        output_path.exists()
        and not overwrite
    ):
        return output_path

    url = COD_CIF_URL.format(
        cod_id=cod_id
    )

    response = requests.get(
        url,
        timeout=timeout,
    )

    response.raise_for_status()

    text = response.text

    # Validate that the downloaded content contains
    # a real CIF data block.
    if re.search(
        r"(?m)^\s*data_\S+",
        text,
    ) is None:
        raise ValueError(
            f"Downloaded content does not look "
            f"like CIF: COD {cod_id}"
        )

    output_path.write_text(
        text,
        encoding="utf-8",
    )
    content_type = (
        response.headers
        .get("content-type", "")
        .lower()
    )

    if (
        "text/html" in content_type
        and "<html" in text.lower()
    ):
        raise ValueError(
            f"COD returned HTML instead of CIF: "
            f"{cod_id}"
        )

    if re.search(
        r"(?m)^\s*data_\S+",
        text,
    ) is None:
        raise ValueError(
            f"Downloaded content does not look "
            f"like CIF: COD {cod_id}"
        )
    return output_path