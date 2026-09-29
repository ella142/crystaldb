from pathlib import Path
import re
import time

import requests


COD_SEARCH_URL = (
    "https://www.crystallography.net/cod/result"
)

COD_CIF_URL = (
    "https://www.crystallography.net/cod/{cod_id}.cif"
)

DEFAULT_TIMEOUT = (10, 45)
DEFAULT_MAX_RETRIES = 4
DEFAULT_BACKOFF_SECONDS = 2

RETRYABLE_STATUS_CODES = {
    429,
    500,
    502,
    503,
    504,
}


def _get_with_retry(
    url,
    *,
    params=None,
    timeout=DEFAULT_TIMEOUT,
    max_retries=DEFAULT_MAX_RETRIES,
    backoff_seconds=DEFAULT_BACKOFF_SECONDS,
):
    """
    GET one URL with retry/backoff.

    Retries:
    - connection errors
    - timeouts
    - HTTP 429
    - HTTP 5xx temporary server errors
    """

    last_error = None

    for attempt in range(
        1,
        max_retries + 1,
    ):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=timeout,
                headers={
                    "User-Agent":
                        "crystaldb/0.1 COD client"
                },
            )

            if (
                response.status_code
                in RETRYABLE_STATUS_CODES
            ):
                response.raise_for_status()

            response.raise_for_status()

            return response

        except (
            requests.Timeout,
            requests.ConnectionError,
            requests.HTTPError,
        ) as exc:
            last_error = exc

            retryable = True

            if isinstance(
                exc,
                requests.HTTPError,
            ):
                status_code = (
                    exc.response.status_code
                    if exc.response is not None
                    else None
                )

                retryable = (
                    status_code
                    in RETRYABLE_STATUS_CODES
                )

            if (
                not retryable
                or attempt >= max_retries
            ):
                raise

            wait_seconds = (
                backoff_seconds
                * (2 ** (attempt - 1))
            )

            print(
                f"[COD] Request failed "
                f"(attempt "
                f"{attempt}/{max_retries}): "
                f"{exc}"
            )

            print(
                f"[COD] Retrying in "
                f"{wait_seconds}s..."
            )

            time.sleep(wait_seconds)

    if last_error is not None:
        raise last_error

    raise RuntimeError(
        "COD request failed unexpectedly."
    )


def search_cod_by_text(
    text,
    timeout=DEFAULT_TIMEOUT,
    max_retries=DEFAULT_MAX_RETRIES,
):
    """
    Search COD broadly by text/mineral name.

    Returns a list of COD IDs.
    """

    response = _get_with_retry(
        COD_SEARCH_URL,
        params={
            "text": text,
            "format": "lst",
        },
        timeout=timeout,
        max_retries=max_retries,
    )

    cod_ids = []

    for line in response.text.splitlines():
        value = line.strip()

        if value.isdigit():
            cod_ids.append(value)

    return cod_ids


def download_cod_cif(
    cod_id,
    output_dir,
    timeout=DEFAULT_TIMEOUT,
    max_retries=DEFAULT_MAX_RETRIES,
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

    response = _get_with_retry(
        url,
        timeout=timeout,
        max_retries=max_retries,
    )

    text = response.text

    content_type = (
        response.headers
        .get("content-type", "")
        .lower()
    )

    # Reject obvious HTML responses before
    # anything is written to disk.
    if (
        "text/html" in content_type
        and "<html" in text.lower()
    ):
        raise ValueError(
            f"COD returned HTML instead "
            f"of CIF: {cod_id}"
        )

    # A valid CIF should contain a data_ block.
    if re.search(
        r"(?m)^\s*data_\S+",
        text,
    ) is None:
        raise ValueError(
            f"Downloaded content does not "
            f"look like CIF: COD {cod_id}"
        )

    output_path.write_text(
        text,
        encoding="utf-8",
    )

    return output_path