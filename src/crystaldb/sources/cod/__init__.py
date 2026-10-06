"""COD download client and single-crystal data parsers."""

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
DEFAULT_REQUEST_DELAY_SECONDS = 0.0

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
    session=None,
    request_delay_seconds=DEFAULT_REQUEST_DELAY_SECONDS,
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
    client = session or requests

    for attempt in range(
        1,
        max_retries + 1,
    ):
        try:
            if request_delay_seconds:
                time.sleep(request_delay_seconds)

            response = client.get(
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


def build_cod_session(*, trust_env=True):
    """Build one reusable COD HTTP session.

    The session deliberately keeps Requests' normal environment-proxy and
    certificate-verification behavior.  v3 owns the request pacing and retry
    policy while this helper provides connection reuse.
    """

    session = requests.Session()
    session.trust_env = trust_env
    session.headers.update(
        {
            "User-Agent": "crystaldb/0.1 COD client",
        }
    )
    return session


def search_cod_by_text(
    text,
    timeout=DEFAULT_TIMEOUT,
    max_retries=DEFAULT_MAX_RETRIES,
    *,
    session=None,
    request_delay_seconds=DEFAULT_REQUEST_DELAY_SECONDS,
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
        session=session,
        request_delay_seconds=request_delay_seconds,
    )

    cod_ids = []

    for line in response.text.splitlines():
        value = line.strip()

        if value.isdigit():
            cod_ids.append(value)

    return cod_ids


def search_cod_targeted(
    text,
    *,
    query_kind=None,
    timeout=DEFAULT_TIMEOUT,
    max_retries=DEFAULT_MAX_RETRIES,
    session=None,
    request_delay_seconds=DEFAULT_REQUEST_DELAY_SECONDS,
):
    """Run one targeted COD text query with URL/provenance retained.

    This is a thin extension of the existing COD client.  It intentionally
    returns the raw response text as well as IDs so a v3 workflow can retain
    the exact query URL and inspect metadata formats without broad-library
    downloads.
    """

    response = _get_with_retry(
        COD_SEARCH_URL,
        params={
            "text": text,
            "format": "lst",
        },
        timeout=timeout,
        max_retries=max_retries,
        session=session,
        request_delay_seconds=request_delay_seconds,
    )

    cod_ids = [
        line.strip()
        for line in response.text.splitlines()
        if line.strip().isdigit()
    ]

    return {
        "query_kind": query_kind,
        "query_text": text,
        "url": response.url,
        "status_code": response.status_code,
        "cod_ids": cod_ids,
        "raw_text": response.text,
    }


def download_cod_cif(
    cod_id,
    output_dir,
    timeout=DEFAULT_TIMEOUT,
    max_retries=DEFAULT_MAX_RETRIES,
    overwrite=False,
    *,
    session=None,
    request_delay_seconds=DEFAULT_REQUEST_DELAY_SECONDS,
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
        session=session,
        request_delay_seconds=request_delay_seconds,
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
