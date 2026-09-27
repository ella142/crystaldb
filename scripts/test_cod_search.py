import requests

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from crystaldb.mongo import get_database
from crystaldb.matching.rruff_signature import (
    build_rruff_signature,
    get_rruff_ideal_chemistry,
)


COD_SEARCH_URL = (
    "https://www.crystallography.net/cod/result"
)


def clean_space_group(value):
    if value is None:
        return None

    return str(value).replace("_", "")


def build_session():
    """
    Build a requests session with retry support.
    """

    retry = Retry(
        total=5,
        connect=5,
        read=5,
        status=5,
        backoff_factor=1.0,
        status_forcelist=[
            429,
            500,
            502,
            503,
            504,
        ],
        allowed_methods=[
            "GET",
        ],
    )

    adapter = HTTPAdapter(
        max_retries=retry
    )

    session = requests.Session()

    session.mount(
        "https://",
        adapter,
    )

    session.mount(
        "http://",
        adapter,
    )

    return session


def main():
    sample_id = "R050336"

    # --------------------------------
    # Connect to RRUFF MongoDB
    # --------------------------------
    rruff_db = get_database(
        database_name="rruff"
    )

    # --------------------------------
    # Load RRUFF DIF document
    # --------------------------------
    dif_doc = rruff_db.dif.find_one(
        {
            "sample_id": sample_id,
        }
    )

    if dif_doc is None:
        print(
            f"No DIF document found for "
            f"{sample_id}"
        )
        return

    # --------------------------------
    # Get ideal chemistry
    # --------------------------------
    ideal_chemistry = (
        get_rruff_ideal_chemistry(
            rruff_db,
            sample_id,
        )
    )

    # --------------------------------
    # Build RRUFF matching signature
    # --------------------------------
    signature = build_rruff_signature(
        dif_doc,
        ideal_chemistry=ideal_chemistry,
    )

    # --------------------------------
    # Prepare COD search
    # --------------------------------
    mineral_name = signature.get(
        "sample_mineral"
    )

    if not mineral_name:
        print(
            f"No sample mineral name found "
            f"for {sample_id}"
        )
        return

    params = {
        "text": mineral_name,
        "format": "lst",
    }

    # --------------------------------
    # Query COD
    # --------------------------------
    session = build_session()

    try:
        response = session.get(
            COD_SEARCH_URL,
            params=params,
            timeout=30,
            headers={
                "User-Agent":
                    "CrystalDB/0.1 "
                    "(RRUFF-COD structure matching)"
            },
        )

        response.raise_for_status()

    except requests.exceptions.SSLError as exc:
        print(
            "COD request failed because of "
            "an SSL/TLS connection error:"
        )
        print(exc)
        return

    except requests.exceptions.Timeout as exc:
        print(
            "COD request timed out:"
        )
        print(exc)
        return

    except requests.exceptions.ConnectionError as exc:
        print(
            "Could not connect to COD:"
        )
        print(exc)
        return

    except requests.exceptions.HTTPError as exc:
        print(
            "COD returned an HTTP error:"
        )
        print(exc)
        return

    except requests.exceptions.RequestException as exc:
        print(
            "COD request failed:"
        )
        print(exc)
        return

    # --------------------------------
    # Parse COD IDs
    # --------------------------------
    cod_ids = [
        line.strip()
        for line in response.text.splitlines()
        if line.strip()
    ]

    # --------------------------------
    # Print result
    # --------------------------------
    print(
        f"RRUFF sample: {sample_id}"
    )

    print(
        f"Mineral: "
        f"{signature.get('sample_mineral')}"
    )

    print(
        f"Ideal chemistry: "
        f"{signature.get('ideal_chemistry')}"
    )

    print(
        f"Space group: "
        f"{signature.get('space_group')}"
    )

    print(
        f"COD candidates found: "
        f"{len(cod_ids)}"
    )

    print("COD IDs:")

    for cod_id in cod_ids[:50]:
        print(
            f"  {cod_id}"
        )


if __name__ == "__main__":
    main()