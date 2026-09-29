from pathlib import Path
import re
import unicodedata

from crystaldb.cif_parser import parse_cif


def _normalize_ascii(value):
    if value is None:
        return ""

    value = unicodedata.normalize(
        "NFKD",
        str(value),
    )

    return (
        value.encode(
            "ascii",
            "ignore",
        )
        .decode("ascii")
        .lower()
    )


def _normalize_token(value):
    value = _normalize_ascii(value)

    return re.sub(
        r"[^a-z0-9]+",
        "",
        value,
    )


def _rruff_author_surnames(text):
    if not isinstance(text, str):
        return set()

    surnames = set()

    for person in text.split(","):
        tokens = re.findall(
            r"[A-Za-z][A-Za-z'’-]*",
            person,
        )

        if not tokens:
            continue

        surname = _normalize_token(
            tokens[0]
        )

        if surname:
            surnames.add(surname)

    return surnames


def _cod_author_surnames(authors):
    if not authors:
        return set()

    if isinstance(authors, str):
        authors = [authors]

    surnames = set()

    for author in authors:
        if not isinstance(author, str):
            continue

        if "," in author:
            surname = author.split(
                ",",
                1,
            )[0]

        else:
            parts = author.split()

            if not parts:
                continue

            surname = parts[0]

        surname = _normalize_token(
            surname
        )

        if surname:
            surnames.add(surname)

    return surnames


def extract_rruff_reference_fingerprints(
    references,
):
    """
    Extract conservative bibliographic
    fingerprints from RRUFF reference data.

    Primary evidence:
    - author surname overlap
    - publication year
    - first/last page
    - volume when available

    Title is deliberately not used as a
    hard matching condition.
    """

    fingerprints = []

    if not isinstance(references, list):
        return fingerprints

    for index, text in enumerate(
        references
    ):
        if not isinstance(text, str):
            continue

        # Preferred form:
        # Journal 56 (1971) 791-823
        match = re.search(
            r"(?P<volume>\d+)\s*"
            r"\((?P<year>\d{4})\)\s*"
            r"(?P<page_first>\d+)\s*"
            r"[-–]\s*"
            r"(?P<page_last>\d+)",
            text,
        )

        volume = None

        if match is not None:
            year = match.group("year")
            page_first = match.group(
                "page_first"
            )
            page_last = match.group(
                "page_last"
            )
            volume = match.group(
                "volume"
            )

        else:
            # Fallback for references where
            # volume is unavailable.
            match = re.search(
                r"\((?P<year>\d{4})\)\s*"
                r"(?P<page_first>\d+)\s*"
                r"[-–]\s*"
                r"(?P<page_last>\d+)",
                text,
            )

            if match is None:
                continue

            year = match.group("year")
            page_first = match.group(
                "page_first"
            )
            page_last = match.group(
                "page_last"
            )

        author_text = ""

        if index > 0:
            previous = references[
                index - 1
            ]

            if isinstance(previous, str):
                author_text = previous

        fingerprints.append(
            {
                "year": year,
                "volume": volume,
                "page_first": page_first,
                "page_last": page_last,
                "authors": sorted(
                    _rruff_author_surnames(
                        author_text
                    )
                ),
                "citation_text": text,
            }
        )

    return fingerprints


def build_cod_publication_fingerprint(
    publication,
):
    if not isinstance(
        publication,
        dict,
    ):
        return None

    return {
        "year": str(
            publication.get(
                "year",
                "",
            )
        ).strip(),

        "volume": str(
            publication.get(
                "volume",
                "",
            )
        ).strip(),

        "page_first": str(
            publication.get(
                "page_first",
                "",
            )
        ).strip(),

        "page_last": str(
            publication.get(
                "page_last",
                "",
            )
        ).strip(),

        "authors": sorted(
            _cod_author_surnames(
                publication.get(
                    "authors"
                )
            )
        ),
    }


def bibliographic_match(
    rruff_fingerprints,
    cod_fingerprint,
):
    """
    Conservative strong bibliography match.

    Required:
    - same year
    - same first and last page
    - at least one shared author surname

    Volume must also agree when both
    sources provide it.
    """

    if cod_fingerprint is None:
        return False

    cod_authors = set(
        cod_fingerprint.get(
            "authors",
            [],
        )
    )

    for reference in rruff_fingerprints:

        if (
            reference["year"]
            != cod_fingerprint["year"]
        ):
            continue

        if (
            reference["page_first"]
            != cod_fingerprint[
                "page_first"
            ]
        ):
            continue

        if (
            reference["page_last"]
            != cod_fingerprint[
                "page_last"
            ]
        ):
            continue

        reference_authors = set(
            reference.get(
                "authors",
                [],
            )
        )

        if not (
            reference_authors
            & cod_authors
        ):
            continue

        reference_volume = (
            reference.get("volume")
        )

        cod_volume = (
            cod_fingerprint.get(
                "volume"
            )
        )

        if (
            reference_volume
            and cod_volume
            and reference_volume
            != cod_volume
        ):
            continue

        return True

    return False


def _candidate_summary(candidate):
    return {
        "source":
            candidate.get("source"),

        "source_id":
            candidate.get("source_id"),

        "file_path":
            candidate.get("file_path"),

        "match_status":
            candidate.get("status"),

        "candidate_type":
            candidate.get(
                "candidate_type"
            ),

        "evidence":
            candidate.get("evidence"),
    }


def resolve_sample_candidates(
    coverage_result,
    dif_doc,
    project_root,
    publication_cache=None,
):
    """
    Resolve already accepted sample_structure
    candidates without changing the underlying
    crystallographic matcher.

    Resolution levels
    -----------------
    record:
        one specific candidate remains

    group:
        bibliography supports multiple
        candidates, but available evidence
        does not justify choosing one record

    review:
        bibliography cannot resolve the
        candidate set
    """

    project_root = Path(project_root)

    if publication_cache is None:
        publication_cache = {}

    sample_id = coverage_result.get(
        "rruff_sample_id"
    )

    candidates = [
        item
        for item in coverage_result.get(
            "matches",
            [],
        )
        if item.get(
            "relation_type"
        ) == "sample_structure"
    ]

    candidate_summaries = [
        _candidate_summary(item)
        for item in candidates
    ]

    base_result = {
        "rruff_sample_id":
            sample_id,

        "sample_structure_candidate_count":
            len(candidates),

        "all_sample_structure_candidates":
            candidate_summaries,
    }

    # ------------------------------------------------
    # No sample-structure candidate
    # ------------------------------------------------

    if not candidates:
        return {
            **base_result,

            "resolution_level":
                "review",

            "resolution_status":
                "no_sample_structure_candidate",

            "selected_candidate":
                None,

            "bibliographic_candidates":
                [],
        }

    # ------------------------------------------------
    # Exactly one candidate after the existing
    # crystallographic filtering stage.
    # ------------------------------------------------

    if len(candidates) == 1:
        return {
            **base_result,

            "resolution_level":
                "record",

            "resolution_status":
                "single_candidate_after_filtering",

            "selected_candidate":
                _candidate_summary(
                    candidates[0]
                ),

            "bibliographic_candidates":
                [],
        }

    # ------------------------------------------------
    # Multiple candidates:
    # use bibliography for narrowing.
    # ------------------------------------------------

    references = []

    if isinstance(dif_doc, dict):
        references = dif_doc.get(
            "references",
            [],
        )

    reference_fingerprints = (
        extract_rruff_reference_fingerprints(
            references
        )
    )

    if not reference_fingerprints:
        return {
            **base_result,

            "resolution_level":
                "review",

            "resolution_status":
                "unparseable_reference",

            "selected_candidate":
                None,

            "bibliographic_candidates":
                [],

            "reference_fingerprints":
                [],
        }

    bibliography_hits = []

    for candidate in candidates:

        file_path = candidate.get(
            "file_path"
        )

        if not file_path:
            continue

        if file_path in publication_cache:
            publication = (
                publication_cache[
                    file_path
                ]
            )

        else:
            parsed = parse_cif(
                project_root
                / file_path
            )

            publication = parsed.get(
                "publication"
            )

            publication_cache[
                file_path
            ] = publication

        cod_fingerprint = (
            build_cod_publication_fingerprint(
                publication
            )
        )

        if bibliographic_match(
            reference_fingerprints,
            cod_fingerprint,
        ):
            bibliography_hits.append(
                _candidate_summary(
                    candidate
                )
            )

    # ------------------------------------------------
    # Bibliography uniquely resolves one record.
    # ------------------------------------------------

    if len(bibliography_hits) == 1:
        return {
            **base_result,

            "resolution_level":
                "record",

            "resolution_status":
                "unique_bibliographic_match",

            "selected_candidate":
                bibliography_hits[0],

            "bibliographic_candidates":
                bibliography_hits,

            "reference_fingerprints":
                reference_fingerprints,
        }

    # ------------------------------------------------
    # Same reference supports multiple CIF records.
    #
    # IMPORTANT:
    # Do not force one CIF and do not claim
    # structural equivalence here.
    # ------------------------------------------------

    if len(bibliography_hits) > 1:
        return {
            **base_result,

            "resolution_level":
                "group",

            "resolution_status":
                "bibliography_supported_candidate_group",

            "selected_candidate":
                None,

            "bibliographic_candidates":
                bibliography_hits,

            "reference_fingerprints":
                reference_fingerprints,
        }

    # ------------------------------------------------
    # Reference exists, but none of the retained
    # sample candidates matches it bibliographically.
    # ------------------------------------------------

    return {
        **base_result,

        "resolution_level":
            "review",

        "resolution_status":
            "no_bibliographic_match",

        "selected_candidate":
            None,

        "bibliographic_candidates":
            [],

        "reference_fingerprints":
            reference_fingerprints,
    }
