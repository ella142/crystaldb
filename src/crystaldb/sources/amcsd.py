from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


AMCSD_SEARCH_URL = "https://www.rruff.net/AMS/result.php"


def normalize_amcsd_id(amcsd_id):
    """
    Normalize AMCSD ID to a 7-digit string.
    Example:
        12672 -> 0012672
        "0012672" -> 0012672
    """
    value = str(amcsd_id).strip()

    if not value.isdigit():
        raise ValueError(
            f"Invalid AMCSD ID: {amcsd_id}"
        )

    return value.zfill(7)


def download_amcsd_cif(
    amcsd_id,
    output_dir,
    timeout=30,
):
    """
    Download one CIF from AMCSD.

    The function first opens the AMCSD result page,
    discovers the CIF download link, then downloads
    and validates the returned file.
    """

    amcsd_id = normalize_amcsd_id(amcsd_id)

    output_dir = Path(output_dir)
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        output_dir
        / f"{amcsd_id}.cif"
    )

    # 1. Search AMCSD by database ID
    response = requests.get(
        AMCSD_SEARCH_URL,
        params={
            "key": (
                "_database_code_amcsd+"
                f"{amcsd_id}"
            ),
            "viewing": "html",
        },
        timeout=timeout,
    )

    response.raise_for_status()

    # 2. Find the CIF download link
    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    cif_link = None

    for link in soup.find_all(
        "a",
        href=True,
    ):
        text = " ".join(
            link.stripped_strings
        )

        if "Download CIF data" in text:
            cif_link = urljoin(
                response.url,
                link["href"],
            )
            break

    if cif_link is None:
        raise RuntimeError(
            "AMCSD record was found, but "
            "no CIF download link was found "
            f"for {amcsd_id}"
        )

    # 3. Download CIF
    cif_response = requests.get(
        cif_link,
        timeout=timeout,
    )

    cif_response.raise_for_status()

    cif_text = cif_response.text

    # 4. Basic validation
    required_markers = [
        "_database_code_amcsd",
        "_cell_length_a",
        "_cell_length_b",
        "_cell_length_c",
    ]

    missing = [
        marker
        for marker in required_markers
        if marker not in cif_text
    ]

    if missing:
        raise RuntimeError(
            "Downloaded content does not look "
            "like an AMCSD CIF. "
            f"Missing: {missing}"
        )

    if amcsd_id not in cif_text:
        raise RuntimeError(
            "Downloaded CIF does not contain "
            f"AMCSD ID {amcsd_id}"
        )

    # 5. Save raw source file
    output_path.write_text(
        cif_text,
        encoding="utf-8",
    )

    return {
        "amcsd_id": amcsd_id,
        "search_url": response.url,
        "download_url": cif_link,
        "file_path": output_path,
        "size_bytes": output_path.stat().st_size,
    }