"""Audit the official PowBase legacy index and its ZIP archives.

This script is deliberately an inventory tool, not an ingestion tool.  It
preserves the downloaded index bytes, keeps each physical source line intact,
and treats ``#``-delimited content as opaque source tokens.  It does not
connect to MongoDB and it never writes below a canonical CrystalDB directory.

Typical usage:

    python scripts/audit_powbase.py

For an already downloaded index (useful on an offline machine):

    python scripts/audit_powbase.py --index-path path/to/powbase.txt

The main reviewable outputs are JSONL files because raw HTML/legacy text and
lists of ZIP members do not fit safely into a fixed relational schema:

    <output>/inventory/powbase_index_inventory.jsonl
    <output>/inventory/powbase_archive_inventory.jsonl
    <output>/inventory/powbase_entry_inventory.csv
    <output>/powbase_audit_manifest.json
"""

from __future__ import annotations

import argparse
import base64
import binascii
import csv
import hashlib
import html
import json
import math
import os
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable
from urllib.parse import unquote, urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INDEX_URL = (
    "https://www.cristal.org/DU-SDPD/nexus/albweb/univ-lem/powbase/powbase.txt"
)
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "archive" / "powbase_20261006"
DEFAULT_INDEX_PATH = DEFAULT_OUTPUT_ROOT / "raw" / "powbase.txt"
DEFAULT_ARCHIVE_DIR = DEFAULT_OUTPUT_ROOT / "archives"
DEFAULT_INVENTORY_DIR = DEFAULT_OUTPUT_ROOT / "inventory"

USER_AGENT = "CrystalDB-PowBase-audit/1.0"
RETRY_STATUS_CODES = (429, 500, 502, 503, 504)
MAX_MEMBER_ANALYSIS_BYTES = 16 * 1024 * 1024
MAX_METADATA_LINES = 500
MAX_TEXT_PREVIEW_CHARS = 4000

HREF_RE = re.compile(
    r"""(?is)\b(?:href|src)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))"""
)
BARE_LINK_RE = re.compile(
    r"""(?ix)
    (?P<link>
        (?:https?://|/|\.{0,2}/)?
        [^\s"'<>#]+
        \.(?:zip|gif|wrl)
        (?:[?#][^\s"'<>]*)?
    )
    """
)
NUMERIC_TOKEN_RE = re.compile(
    r"""^[+-]?(?:
        (?:\d+(?:\.\d*)?)|
        (?:\.\d+)
    )(?:[EeDd][+-]?\d+)?$""",
    re.VERBOSE,
)
ID_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
FORMULA_NAME_TOKEN_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.()+\-*/×·{}[\]]{0,79}$"
)
CIF_TAG_RE = re.compile(r"^\s*(_[A-Za-z0-9_.]+)")
KEY_VALUE_RE = re.compile(
    r"""^\s*(?:[#;!]|//)?\s*([A-Za-z][A-Za-z0-9_. -]{1,80})\s*[:=]\s*(\S.*)$"""
)
CIF_COMMENTED_TAG_RE = re.compile(
    r"""^\s*(?P<prefix>[!#])\s*(?P<tag>_[A-Za-z0-9_.]+)\b(?P<value>.*)$"""
)
CIF_COMMENTED_LOOP_TAG_RE = re.compile(
    r"""^\s*(?P<prefix>[!#])\s*loop_\s+(?P<tag>_[A-Za-z0-9_.]+)\b(?P<value>.*)$""",
    re.IGNORECASE,
)
CIF_COMMENTED_LOOP_RE = re.compile(
    r"""^\s*[!#]\s*loop_\s*$""",
    re.IGNORECASE,
)
CIF_DATA_BLOCK_RE = re.compile(
    r"""^\s*[!#]\s*data_(?P<block>\S+)\s*$""",
    re.IGNORECASE,
)
FULLPROF_PHASE_RE = re.compile(
    r"""(?i)\bdata\s+for\s+phase\s+number\s*:\s*(\d+)"""
)
FULLPROF_COMM_RE = re.compile(
    r"""(?i)^\s*[!#]\s*comm\b(?P<value>.*)$"""
)
FULLPROF_WAVELENGTH_LABEL_RE = re.compile(
    r"""(?i)\blambda1\b.*\blambda2\b"""
)
PHASE_TOKEN_RE = re.compile(
    r"""(?i)\bPHASE[_\s-]?(\d+)\b"""
)
DATA_PHASE_TOKEN_RE = re.compile(
    r"""(?i)\bdata_[^ ]*phase[_-]?(\d+)\b"""
)
DIFFRACTION_WORD_RE = re.compile(
    r"""(?ix)
    diffraction|powder|xrd|2\s*theta|two[-\s]*theta|intensit(?:y|ies)|
    counts?|d[-\s]*spacing|bragg|scan
    """
)
OPAQUE_BINARY_EXTENSIONS = {
    ".raw",
    ".bin",
    ".datx",
    ".nxs",
    ".h5",
    ".hdf5",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part_path = path.with_name(path.name + ".part")
    part_path.write_bytes(data)
    os.replace(part_path, path)


def write_text_atomic(path: Path, text: str) -> None:
    write_bytes_atomic(path, text.encode("utf-8"))


def write_json_atomic(path: Path, value: Any) -> None:
    write_text_atomic(
        path,
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
    )


def build_session(max_retries: int) -> requests.Session:
    retry = Retry(
        total=max_retries,
        connect=max_retries,
        read=max_retries,
        status=max_retries,
        backoff_factor=1.0,
        status_forcelist=RETRY_STATUS_CODES,
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def decode_legacy_bytes(data: bytes) -> tuple[str, str]:
    """Decode for parsing while retaining the original bytes separately.

    Latin-1 is the final candidate because it is a one-to-one byte mapping.
    The corresponding base64 field on each record is the canonical byte-level
    preservation mechanism; the decoded text is a readable representation.
    """

    candidates = ("utf-8-sig", "cp1252", "iso-8859-1")
    best_text = data.decode("iso-8859-1")
    best_encoding = "iso-8859-1"
    best_score = float("-inf")

    for encoding in candidates:
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        control_count = sum(
            1
            for char in text
            if ord(char) < 32 and char not in "\r\n\t"
        )
        replacement_count = text.count("\ufffd")
        score = len(text) - control_count * 20 - replacement_count * 50
        if score > best_score:
            best_score = score
            best_text = text
            best_encoding = encoding

    return best_text, best_encoding


def split_source_lines(data: bytes, text: str) -> list[tuple[bytes, str, str]]:
    """Return (raw_bytes, decoded_line_without_eol, raw_eol) records."""

    raw_lines = data.splitlines(keepends=True)
    decoded_lines = text.splitlines(keepends=True)
    # The byte and text splitters should agree for ordinary legacy text.  If a
    # malformed byte sequence makes them disagree, fall back to byte-oriented
    # line splitting so every source byte remains represented.
    if len(raw_lines) != len(decoded_lines):
        records: list[tuple[bytes, str, str]] = []
        for raw_line in raw_lines:
            if raw_line.endswith(b"\r\n"):
                body, eol = raw_line[:-2], "\r\n"
            elif raw_line.endswith(b"\n") or raw_line.endswith(b"\r"):
                body, eol = raw_line[:-1], raw_line[-1:].decode("ascii")
            else:
                body, eol = raw_line, ""
            decoded_body, _ = decode_legacy_bytes(body)
            records.append((raw_line, decoded_body, eol))
        return records

    records = []
    for raw_line, decoded_line in zip(raw_lines, decoded_lines):
        if decoded_line.endswith("\r\n"):
            body, eol = decoded_line[:-2], "\r\n"
        elif decoded_line.endswith("\n") or decoded_line.endswith("\r"):
            body, eol = decoded_line[:-1], decoded_line[-1]
        else:
            body, eol = decoded_line, ""
        records.append((raw_line, body, eol))
    return records


class AnchorTextParser(HTMLParser):
    """Collect raw-ish anchor hrefs and their visible text from one line."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.anchors: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = next(
            (
                value
                for key, value in attrs
                if key.lower() == "href" and value is not None
            ),
            "",
        )
        self._current = {"href": href, "text": ""}

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self._current is not None:
            self._current["text"] += data

    def handle_entityref(self, name: str) -> None:
        if self._current is not None:
            self._current["text"] += f"&{name};"

    def handle_charref(self, name: str) -> None:
        if self._current is not None:
            self._current["text"] += f"&#{name};"

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._current is not None:
            self.anchors.append(self._current)
            self._current = None


def extract_anchor_records(line: str) -> list[dict[str, str]]:
    parser = AnchorTextParser()
    try:
        parser.feed(line)
        parser.close()
    except Exception:
        # Regex extraction below still handles malformed legacy HTML.
        parser.anchors = []

    records = list(parser.anchors)
    if records:
        return records

    for match in HREF_RE.finditer(line):
        href = next((group for group in match.groups() if group is not None), "")
        records.append({"href": html.unescape(href), "text": ""})
    return records


def extract_raw_links(line: str) -> list[str]:
    links: list[str] = []
    for match in HREF_RE.finditer(line):
        href = next((group for group in match.groups() if group is not None), "")
        if href:
            links.append(html.unescape(href))
    links.extend(match.group("link") for match in BARE_LINK_RE.finditer(line))

    result: list[str] = []
    seen: set[str] = set()
    for link in links:
        if link not in seen:
            result.append(link)
            seen.add(link)
    return result


def normalize_link(link: str, index_url: str) -> str:
    return urljoin(index_url, html.unescape(link.strip()))


def link_path(link: str, index_url: str) -> str:
    return urlparse(normalize_link(link, index_url)).path


def is_suffix_link(link: str, suffix: str, index_url: str) -> bool:
    return link_path(link, index_url).lower().endswith(suffix.lower())


def strip_html_text(value: str) -> str:
    value = re.sub(r"(?is)<script\b.*?</script>", " ", value)
    value = re.sub(r"(?is)<style\b.*?</style>", " ", value)
    value = re.sub(r"(?s)<[^>]*>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def safe_entry_id_from_url(url: str) -> str | None:
    path = unquote(urlparse(url).path)
    filename = path.rsplit("/", 1)[-1]
    if not filename.lower().endswith(".zip"):
        return None
    stem = filename[:-4]
    return stem if ID_TOKEN_RE.fullmatch(stem) else None


def apparent_token_from_line(
    line: str,
    entry_id: str | None,
    anchors: list[dict[str, str]],
    zip_links: list[dict[str, str]],
) -> tuple[str | None, str | None]:
    """Return only a conservative, visibly separable formula/name token."""

    anchor_candidates: list[tuple[str, str]] = []
    field_candidates: list[tuple[str, str]] = []
    hash_parts = line.split("#")
    if len(hash_parts) > 1:
        first_hash_field = strip_html_text(hash_parts[1]).strip()
        if (
            first_hash_field
            and len(first_hash_field) <= 80
            and first_hash_field.casefold() != "unknown"
            and not first_hash_field.casefold().endswith((".zip", ".gif", ".wrl"))
            and not re.search(r"(?i)\b(?:mailto|href|http|www\.)\b", first_hash_field)
        ):
            field_candidates.append(
                (first_hash_field, "first_hash_delimited_field")
            )

    for anchor in zip_links:
        label = strip_html_text(
            anchor.get("text", anchor.get("anchor_text", ""))
        )
        if not label:
            continue
        if entry_id and label.casefold() in {
            entry_id.casefold(),
            f"{entry_id}.zip".casefold(),
        }:
            continue
        if label.casefold() in {"zip", "download", "file", "data"}:
            continue
        if len(label) <= 80 and FORMULA_NAME_TOKEN_RE.fullmatch(label):
            anchor_candidates.append((label, "zip_anchor_text"))

    first_hash = line.find("#")
    prefix = line if first_hash < 0 else line[:first_hash]
    visible_prefix = strip_html_text(prefix)
    if entry_id:
        visible_prefix = re.sub(
            rf"(?i)\b{re.escape(entry_id)}(?:\.zip)?\b",
            " ",
            visible_prefix,
        )
    visible_prefix = re.sub(r"https?://\S+|/\S+\.zip\b", " ", visible_prefix)
    visible_prefix = re.sub(r"\s+", " ", visible_prefix).strip(" -:;,")
    if (
        visible_prefix
        and len(visible_prefix) <= 80
        and FORMULA_NAME_TOKEN_RE.fullmatch(visible_prefix)
    ):
        field_candidates.append((visible_prefix, "pre_hash_visible_text"))

    for candidates in (anchor_candidates, field_candidates):
        unique = {(value, source) for value, source in candidates}
        values = {value for value, _ in unique}
        if len(values) == 1:
            value = next(iter(values))
            source = next(source for candidate, source in unique if candidate == value)
            return value, source
    return None, None


def parse_index_record(
    *,
    line_number: int,
    raw_bytes: bytes,
    raw_line: str,
    raw_eol: str,
    index_url: str,
) -> dict[str, Any] | None:
    anchors = extract_anchor_records(raw_line)
    raw_links = extract_raw_links(raw_line)
    href_records = [
        {"href": href, "text": ""}
        for href in raw_links
        if not any(anchor.get("href") == href for anchor in anchors)
    ]
    all_links = anchors + href_records

    zip_links: list[dict[str, str]] = []
    gif_links: list[str] = []
    wrl_links: list[str] = []
    for link_record in all_links:
        href = link_record.get("href", "")
        if not href:
            continue
        normalized = normalize_link(href, index_url)
        if is_suffix_link(href, ".zip", index_url):
            zip_links.append(
                {
                    "raw_href": href,
                    "url": normalized,
                    "anchor_text": link_record.get("text", ""),
                }
            )
        elif is_suffix_link(href, ".gif", index_url):
            gif_links.append(normalized)
        elif is_suffix_link(href, ".wrl", index_url):
            wrl_links.append(normalized)

    if not zip_links:
        return None

    zip_url = zip_links[0]["url"]
    entry_id = safe_entry_id_from_url(zip_url)
    if entry_id is None:
        return None

    raw_hash_tokens = raw_line.split("#")[1:]
    first_hash = raw_line.find("#")
    raw_tail = raw_line[first_hash:] if first_hash >= 0 else ""
    apparent_token, apparent_source = apparent_token_from_line(
        raw_line,
        entry_id,
        anchors,
        zip_links,
    )

    raw_text_encoding = "iso-8859-1"
    decoded_line, candidate_encoding = decode_legacy_bytes(raw_bytes)
    if decoded_line.endswith("\r\n"):
        decoded_line = decoded_line[:-2]
    elif decoded_line.endswith("\r") or decoded_line.endswith("\n"):
        decoded_line = decoded_line[:-1]
    raw_text_encoding = candidate_encoding

    return {
        "line_number": line_number,
        "entry_id": entry_id,
        "zip_url": zip_url,
        "zip_raw_href": zip_links[0]["raw_href"],
        "zip_links_on_same_line": zip_links,
        "raw_index_text": raw_line + raw_eol,
        "raw_index_text_without_line_ending": raw_line,
        "raw_index_bytes_base64": base64.b64encode(raw_bytes).decode("ascii"),
        "raw_index_text_encoding": raw_text_encoding,
        "raw_line_ending": raw_eol,
        "apparent_formula_name_token": apparent_token,
        "apparent_formula_name_token_source": apparent_source,
        "raw_hash_delimited_tokens": raw_hash_tokens,
        "raw_hash_delimited_token_count": len(raw_hash_tokens),
        "raw_bibliographic_comment_text": raw_tail,
        "raw_visible_text": strip_html_text(raw_line),
        "optional_gif_links": sorted(set(gif_links)),
        "optional_wrl_links": sorted(set(wrl_links)),
        "all_raw_links": raw_links,
    }


def parse_index_bytes(data: bytes, index_url: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    text, encoding = decode_legacy_bytes(data)
    records: list[dict[str, Any]] = []
    ignored_candidate_lines: list[int] = []
    for line_number, (raw_bytes, raw_line, raw_eol) in enumerate(
        split_source_lines(data, text),
        start=1,
    ):
        record = parse_index_record(
            line_number=line_number,
            raw_bytes=raw_bytes,
            raw_line=raw_line,
            raw_eol=raw_eol,
            index_url=index_url,
        )
        if record is not None:
            records.append(record)
        elif ".zip" in raw_line.casefold():
            ignored_candidate_lines.append(line_number)

    by_id = Counter(record["entry_id"] for record in records)
    summary = {
        "source_line_count": len(data.splitlines()),
        "source_byte_count": len(data),
        "source_sha256": sha256_bytes(data),
        "decoded_text_encoding": encoding,
        "index_entry_count": len(records),
        "unique_entry_id_count": len(by_id),
        "duplicate_entry_ids": sorted(
            entry_id for entry_id, count in by_id.items() if count > 1
        ),
        "ignored_zip_candidate_line_numbers": ignored_candidate_lines,
    }
    return records, summary


def download_bytes(
    session: requests.Session,
    url: str,
    destination: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    if destination.is_file() and destination.stat().st_size > 0:
        return {
            "status": "skipped_existing",
            "url": url,
            "path": str(destination.resolve()),
            "size_bytes": destination.stat().st_size,
            "sha256": sha256_file(destination),
        }

    try:
        response = session.get(
            url,
            timeout=(timeout_seconds, timeout_seconds),
        )
        response.raise_for_status()
        content = response.content
        if not content:
            raise IOError("empty HTTP response")
        write_bytes_atomic(destination, content)
        return {
            "status": "downloaded",
            "url": url,
            "path": str(destination.resolve()),
            "size_bytes": len(content),
            "sha256": sha256_bytes(content),
            "http_status": response.status_code,
            "content_type": response.headers.get("content-type"),
        }
    except Exception as exc:
        return {
            "status": "error",
            "url": url,
            "path": str(destination.resolve()),
            "size_bytes": 0,
            "sha256": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def download_index(
    session: requests.Session,
    index_url: str,
    index_path: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    result = download_bytes(session, index_url, index_path, timeout_seconds)
    result["source_kind"] = "official_remote_index"
    return result


def sanitize_filename(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return sanitized or "unknown"


def is_text_like(data: bytes) -> bool:
    if not data:
        return True
    sample = data[: min(len(data), 65536)]
    if b"\x00" in sample:
        return False
    printable = sum(
        1
        for byte in sample
        if byte in b"\t\r\n" or 32 <= byte <= 126 or byte >= 128
    )
    return printable / len(sample) >= 0.85


def decode_member_text(data: bytes) -> tuple[str | None, str | None]:
    if not is_text_like(data):
        return None, None
    for encoding in ("utf-8-sig", "cp1252", "iso-8859-1"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return data.decode("iso-8859-1"), "iso-8859-1"


def strip_comment_prefix(line: str) -> str:
    """Remove only legacy comment markers for parsing, never for storage."""

    return re.sub(r"^\s*[!#]+\s?", "", line)


def unquote_source_value(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1]:
        if stripped[0] in {'"', "'"}:
            return stripped[1:-1]
    return stripped


def split_numeric_tokens(
    line: str,
    *,
    minimum_tokens: int = 1,
    exact_tokens: int | None = None,
) -> list[str] | None:
    candidate = line.strip()
    if not candidate or candidate.startswith(("#", ";", "!", "//")):
        return None
    candidate = re.sub(r"[,;]+", " ", candidate)
    tokens = candidate.split()
    if exact_tokens is not None and len(tokens) != exact_tokens:
        return None
    if len(tokens) < minimum_tokens:
        return None
    if not all(NUMERIC_TOKEN_RE.fullmatch(token) for token in tokens):
        return None
    return tokens


def numeric_token_value(token: str) -> float | None:
    try:
        return float(token.replace("D", "E").replace("d", "e"))
    except (TypeError, ValueError):
        return None


def collect_numeric_rows(
    lines: list[str],
    start_index: int,
) -> dict[str, Any]:
    rows: list[list[str]] = []
    line_numbers: list[int] = []
    for index in range(start_index, len(lines)):
        line = lines[index]
        if not line.strip():
            if rows:
                continue
            continue
        tokens = split_numeric_tokens(line)
        if tokens is None:
            break
        rows.append(tokens)
        line_numbers.append(index + 1)

    values = [token for row in rows for token in row]
    column_counts = Counter(len(row) for row in rows)
    dominant_columns = (
        column_counts.most_common(1)[0][0] if column_counts else None
    )
    return {
        "rows": rows,
        "line_numbers": line_numbers,
        "values": values,
        "numeric_value_count": len(values),
        "numeric_row_count": len(rows),
        "numeric_column_counts": dict(sorted(column_counts.items())),
        "dominant_numeric_column_count": dominant_columns,
    }


def inspect_numeric_array(text: str) -> dict[str, Any]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        tokens = split_numeric_tokens(line)
        if tokens is not None:
            rows.append(tokens)

    column_counts = Counter(len(row) for row in rows)
    dominant_columns = (
        column_counts.most_common(1)[0][0] if column_counts else None
    )
    return {
        "numeric_array_present": bool(rows),
        "numeric_row_count": len(rows),
        "numeric_value_count": sum(len(row) for row in rows),
        "numeric_column_counts": dict(sorted(column_counts.items())),
        "dominant_numeric_column_count": dominant_columns,
        "numeric_array_preview_rows": rows[:5],
    }


def _append_metadata_line(
    metadata_lines: list[str],
    line: str,
) -> None:
    if len(metadata_lines) < MAX_METADATA_LINES:
        metadata_lines.append(line)


def collect_text_metadata(text: str) -> dict[str, Any]:
    metadata_lines: list[str] = []
    metadata_keys: list[str] = []
    cif_tag_records: list[dict[str, Any]] = []
    data_block_names: list[str] = []
    loop_marker_count = 0

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        data_block_match = CIF_DATA_BLOCK_RE.match(line)
        if data_block_match:
            data_block_names.append(data_block_match.group("block"))
            _append_metadata_line(metadata_lines, line)
            continue

        loop_tag_match = CIF_COMMENTED_LOOP_TAG_RE.match(line)
        if loop_tag_match:
            record = {
                "tag": loop_tag_match.group("tag"),
                "raw_value_text": loop_tag_match.group("value").strip(),
                "raw_line": line,
                "comment_prefix": loop_tag_match.group("prefix"),
                "inline_loop_tag": True,
            }
            cif_tag_records.append(record)
            metadata_keys.append(record["tag"])
            _append_metadata_line(metadata_lines, line)
            continue

        if CIF_COMMENTED_LOOP_RE.match(line):
            loop_marker_count += 1
            _append_metadata_line(metadata_lines, line)
            continue

        tag_match = CIF_COMMENTED_TAG_RE.match(line)
        if tag_match:
            record = {
                "tag": tag_match.group("tag"),
                "raw_value_text": tag_match.group("value").strip(),
                "raw_line": line,
                "comment_prefix": tag_match.group("prefix"),
                "inline_loop_tag": False,
            }
            cif_tag_records.append(record)
            metadata_keys.append(record["tag"])
            _append_metadata_line(metadata_lines, line)
            continue

        if stripped.startswith(("#", ";", "!")):
            _append_metadata_line(metadata_lines, line)
            continue

        key_value = KEY_VALUE_RE.match(line)
        if key_value:
            metadata_keys.append(key_value.group(1).strip())
            _append_metadata_line(metadata_lines, line)

    cif_tags = sorted({record["tag"] for record in cif_tag_records})
    radiation_probe_records = [
        record
        for record in cif_tag_records
        if record["tag"].casefold() == "_pd_instr_radiation_probe"
    ]
    wavelength_records = [
        record
        for record in cif_tag_records
        if record["tag"].casefold() == "_diffrn_radiation_wavelength"
    ]
    two_theta_records = [
        record
        for record in cif_tag_records
        if re.search(r"(?i)_pd_(?:meas|proc)_2theta_range_(?:min|max|inc)$", record["tag"])
    ]
    intensity_loop_tags = [
        record["tag"]
        for record in cif_tag_records
        if "intensity" in record["tag"].casefold()
    ]
    phase_block_records = [
        record
        for record in cif_tag_records
        if record["tag"].casefold() in {"_pd_phase_block_id", "_pd_block_id"}
    ]
    phase_name_records = [
        record
        for record in cif_tag_records
        if record["tag"].casefold() == "_pd_phase_name"
    ]

    phase_identifiers: set[str] = set()
    phase_names: list[str] = []
    for block_name in data_block_names:
        match = DATA_PHASE_TOKEN_RE.search(f"data_{block_name}")
        if match:
            phase_identifiers.add(f"PHASE_{match.group(1)}")
    for record in phase_block_records:
        value = unquote_source_value(record["raw_value_text"])
        match = PHASE_TOKEN_RE.search(value)
        if match:
            phase_identifiers.add(f"PHASE_{match.group(1)}")
    for record in phase_name_records:
        value = unquote_source_value(record["raw_value_text"])
        if value:
            phase_names.append(value)
        match = PHASE_TOKEN_RE.search(value)
        if match:
            phase_identifiers.add(f"PHASE_{match.group(1)}")

    return {
        "additional_metadata_present": bool(
            metadata_lines or cif_tag_records or data_block_names
        ),
        "metadata_line_count": len(metadata_lines),
        "metadata_lines": metadata_lines,
        "metadata_key_tokens": sorted(set(metadata_keys)),
        "cif_tag_tokens": cif_tags,
        "cif_tag_records": cif_tag_records,
        "cif_data_block_names": data_block_names,
        "cif_loop_marker_count": loop_marker_count,
        "source_radiation_probe_records": radiation_probe_records,
        "source_wavelength_records": wavelength_records,
        "source_two_theta_range_records": two_theta_records,
        "source_intensity_loop_tags": sorted(set(intensity_loop_tags)),
        "phase_block_identifiers": sorted(phase_identifiers),
        "source_phase_names": list(dict.fromkeys(phase_names)),
    }


def collect_fullprof_metadata(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    fullprof_evidence: list[str] = []
    phase_identifiers: set[str] = set()
    phase_names: list[str] = []
    source_identity_tokens: list[str] = []
    wavelength_records: list[dict[str, Any]] = []

    for index, line in enumerate(lines):
        if re.search(
            r"(?i)\b(?:fullprof|pcr-file|job\s+npr|lambda1|thmin\s+step\s+thmax)\b",
            line,
        ):
            fullprof_evidence.append(line)

        phase_match = FULLPROF_PHASE_RE.search(line)
        if phase_match:
            phase_identifier = f"PHASE_{phase_match.group(1)}"
            phase_identifiers.add(phase_identifier)
            for following in lines[index + 1 : index + 8]:
                candidate = following.strip()
                if not candidate or not candidate.startswith(("#", "!")):
                    continue
                candidate = strip_comment_prefix(following).strip()
                if not candidate or candidate.startswith(("!", "-")):
                    continue
                if candidate.casefold().startswith(
                    ("nat ", "i ", "scale ", "atom ", "u ", "a ")
                ):
                    continue
                phase_names.append(unquote_source_value(candidate))
                break

        comm_match = FULLPROF_COMM_RE.match(line)
        if comm_match:
            value = comm_match.group("value").strip()
            if value:
                source_identity_tokens.append(value.split()[0])

        if FULLPROF_WAVELENGTH_LABEL_RE.search(line):
            labels = re.findall(r"(?i)\b(lambda1|lambda2)\b", line)
            for following in lines[index + 1 : index + 4]:
                candidate = strip_comment_prefix(following)
                values = split_numeric_tokens(candidate, minimum_tokens=2)
                if values is None:
                    continue
                for label, value in zip(labels, values):
                    wavelength_records.append(
                        {
                            "label": label,
                            "raw_value_text": value,
                            "raw_line": following,
                            "source_label_line": line,
                        }
                    )
                break

    return {
        "fullprof_style_evidence": list(dict.fromkeys(fullprof_evidence)),
        "fullprof_phase_block_identifiers": sorted(phase_identifiers),
        "fullprof_phase_names": list(dict.fromkeys(phase_names)),
        "fullprof_source_identity_tokens": list(
            dict.fromkeys(source_identity_tokens)
        ),
        "fullprof_wavelength_records": wavelength_records,
        "is_fullprof_style": bool(fullprof_evidence or phase_identifiers),
    }


def find_intensity_header_and_block(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    candidates: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        tokens = split_numeric_tokens(line, exact_tokens=3)
        if tokens is None:
            continue
        values = [numeric_token_value(token) for token in tokens]
        if any(value is None for value in values):
            continue
        start, step, end = values
        block = collect_numeric_rows(lines, index + 1)
        if not block["values"]:
            continue

        finite = all(
            value is not None and math.isfinite(value)
            for value in (start, step, end)
        )
        ordered = bool(finite and step is not None and step > 0 and end > start)
        expected = None
        grid_aligned = False
        if ordered:
            ratio = (end - start) / step
            expected = round(ratio) + 1
            grid_aligned = math.isclose(
                ratio,
                expected - 1,
                rel_tol=1e-9,
                abs_tol=1e-6,
            )

        raw_count = block["numeric_value_count"]
        trailing_zero_count = 0
        for token in reversed(block["values"]):
            value = numeric_token_value(token)
            if value == 0:
                trailing_zero_count += 1
            else:
                break
        observed_count = raw_count
        observed_count_without_terminal_zeros = (
            raw_count - trailing_zero_count
        )
        trailing_zero_candidate = bool(
            trailing_zero_count > 0
            and expected is not None
            and observed_count_without_terminal_zeros == expected
        )
        dominant_columns = block["dominant_numeric_column_count"]
        fixed_width_padding_candidate = bool(
            trailing_zero_candidate
            and dominant_columns
            and len(block["rows"]) > 0
            and len(block["rows"][-1]) == dominant_columns
            and len(block["numeric_column_counts"]) == 1
            and raw_count % dominant_columns == 0
            and trailing_zero_count <= dominant_columns
        )
        point_count_consistency = (
            bool(
                ordered
                and expected is not None
                and (
                    observed_count == expected
                    or trailing_zero_candidate
                )
            )
            if expected is not None
            else None
        )
        review_reasons: list[str] = []
        if not finite:
            review_reasons.append("header contains non-finite numeric values")
        if not ordered:
            review_reasons.append(
                "header requires finite values with step > 0 and end > start"
            )
        if expected is not None and observed_count != expected:
            review_reasons.append(
                "raw observed intensity count "
                f"({observed_count}) differs from expected point count ({expected})"
            )
            if trailing_zero_candidate:
                review_reasons.append(
                    "terminal zero run is a padding candidate only; "
                    f"excluding it gives {observed_count_without_terminal_zeros} "
                    "points, matching the implied grid"
                )

        candidates.append(
            {
                "header_line_number": index + 1,
                "header_raw_text": line,
                "two_theta_start_raw": tokens[0],
                "step_raw": tokens[1],
                "two_theta_end_raw": tokens[2],
                "two_theta_start": start,
                "step": step,
                "two_theta_end": end,
                "header_values_valid": bool(ordered),
                "grid_alignment_exact": bool(grid_aligned),
                "expected_point_count": expected,
                "raw_numeric_value_count": raw_count,
                "observed_intensity_count": observed_count,
                "observed_intensity_count_excluding_trailing_zero_padding": (
                    observed_count_without_terminal_zeros
                ),
                "trailing_zero_padding_count": trailing_zero_count,
                "trailing_zero_padding_candidate": trailing_zero_candidate,
                "fixed_width_padding_candidate": fixed_width_padding_candidate,
                "trailing_zero_padding_review_reason": (
                    (
                        "terminal zero run completes a uniform "
                        f"{dominant_columns}-value final row; fixed-width "
                        "padding candidate retained for audit only"
                    )
                    if fixed_width_padding_candidate
                    else (
                        "terminal zero run makes the observed count exactly "
                        "match the implied grid; retained as a padding "
                        "candidate for audit only"
                    )
                    if trailing_zero_candidate
                    else (
                        "terminal zero run does not resolve the implied-grid "
                        "count mismatch"
                        if trailing_zero_count > 0
                        else None
                    )
                ),
                "point_count_consistency": point_count_consistency,
                "point_count_review_reasons": review_reasons,
                "data_line_count": block["numeric_row_count"],
                "data_column_counts": block["numeric_column_counts"],
                "dominant_data_column_count": block["dominant_numeric_column_count"],
                "data_line_numbers": block["line_numbers"],
            }
        )

    if not candidates:
        return {
            "header_found": False,
            "header_candidate_count": 0,
            "point_count_review_reasons": [
                "no three-number intensity header followed by numeric rows was found"
            ],
        }

    selected = max(
        candidates,
        key=lambda candidate: (
            bool(candidate["point_count_consistency"]),
            bool(candidate["header_values_valid"]),
            candidate["raw_numeric_value_count"],
            -candidate["header_line_number"],
        ),
    )
    return {
        **selected,
        "header_found": True,
        "header_candidate_count": len(candidates),
    }


def is_formula_like_token(value: str) -> bool:
    normalized = re.sub(r"\s+", "", unquote_source_value(value))
    return bool(
        re.fullmatch(
            r"(?:[A-Z][a-z]?(?:\d+(?:\.\d+)?)?)+(?:[+-])?",
            normalized,
        )
    )


def build_metadata_conflict(
    *,
    entry: dict[str, Any],
    metadata: dict[str, Any],
    fullprof: dict[str, Any],
    content_family: str,
) -> tuple[bool, list[str]]:
    notes: list[str] = []
    index_token = (entry.get("apparent_formula_name_token") or "").strip()
    embedded_tokens = [
        token
        for token in (
            fullprof.get("fullprof_source_identity_tokens") or []
        )
        if is_formula_like_token(token)
    ]
    embedded_tokens.extend(
        token
        for token in (fullprof.get("fullprof_phase_names") or [])
        if is_formula_like_token(token)
    )

    unique_embedded = list(dict.fromkeys(embedded_tokens))
    if content_family == "fullprof_style_pattern" and len(unique_embedded) > 1:
        notes.append(
            "embedded FullProf identity tokens disagree: "
            + ", ".join(unique_embedded)
        )
    if (
        content_family == "fullprof_style_pattern"
        and index_token
        and is_formula_like_token(index_token)
    ):
        mismatched = [
            token
            for token in unique_embedded
            if token.casefold() != index_token.casefold()
        ]
        if mismatched:
            notes.append(
                f"index token {index_token!r} coexists with embedded source token(s): "
                + ", ".join(mismatched)
            )

    return bool(notes), notes


def classify_content_family(
    *,
    text: str,
    metadata: dict[str, Any],
    fullprof: dict[str, Any],
    pattern: dict[str, Any],
    numeric_summary: dict[str, Any],
) -> str:
    cif_tags = metadata.get("cif_tag_tokens") or []
    has_commented_pdcif = bool(
        cif_tags
        and any(
            tag.casefold().startswith(
                ("_pd_", "_diffrn_", "_publ_", "_cell_", "_symmetry_")
            )
            for tag in cif_tags
        )
    ) or bool(metadata.get("cif_data_block_names"))
    if has_commented_pdcif:
        return "commented_pdcif"
    if fullprof.get("is_fullprof_style"):
        return "fullprof_style_pattern"
    if pattern.get("header_found"):
        return "legacy_intensity_array"
    if numeric_summary.get("numeric_array_present"):
        return "numeric_unknown"
    if text.strip():
        return "other"
    return "other"


def diffraction_status(
    *,
    text: str | None,
    pattern: dict[str, Any] | None,
    numeric_summary: dict[str, Any] | None,
) -> tuple[bool | None, str]:
    if text is None:
        return None, "opaque_or_binary_member"
    if pattern and pattern.get("header_found"):
        if pattern.get("point_count_consistency") is True:
            return (
                True,
                "three-number start/step/end header and observed grid count "
                "are consistent after audit-only trailing-zero padding check",
            )
        return (
            None,
            "; ".join(pattern.get("point_count_review_reasons") or [])
            or "intensity header found but grid compatibility is unresolved",
        )
    if numeric_summary and numeric_summary.get("numeric_array_present"):
        return None, "numeric rows found without a validated intensity header"
    return False, "no numeric diffraction-array evidence detected"


def inspect_member(
    archive: zipfile.ZipFile | None,
    info: Any,
    entry: dict[str, Any] | None = None,
    raw_override: bytes | None = None,
) -> dict[str, Any]:
    filename = info.filename
    suffix = Path(filename).suffix
    record: dict[str, Any] = {
        "member_filename": filename,
        "is_directory": info.is_dir(),
        "actual_extension": suffix,
        "extension_lower": suffix.casefold(),
        "source_extension": suffix,
        "file_size_bytes": info.file_size,
        "compressed_size_bytes": info.compress_size,
        "crc32": f"{info.CRC:08x}",
        "member_sha256": None,
        "content_read_status": "not_read",
        "text_decode_encoding": None,
        "text_preview": None,
        "analysis_truncated": False,
        "numeric_array_present": None,
        "numeric_row_count": None,
        "numeric_value_count": None,
        "numeric_column_counts": {},
        "dominant_numeric_column_count": None,
        "detected_content_family": "other",
        "diffraction_array": None,
        "diffraction_arrays_present": None,
        "diffraction_array_basis": "not_inspected",
        "experimental_profile_parse_status": "not_assessed",
        "header_found": False,
        "header_candidate_count": 0,
        "header_raw_text": None,
        "two_theta_start_raw": None,
        "step_raw": None,
        "two_theta_end_raw": None,
        "grid_alignment_exact": None,
        "expected_point_count": None,
        "raw_numeric_value_count": None,
        "observed_intensity_count": None,
        "observed_intensity_count_excluding_trailing_zero_padding": None,
        "trailing_zero_padding_count": 0,
        "trailing_zero_padding_candidate": False,
        "fixed_width_padding_candidate": False,
        "trailing_zero_padding_review_reason": None,
        "point_count_consistency": None,
        "point_count_review_reasons": [],
        "data_line_count": 0,
        "data_column_counts": {},
        "dominant_data_column_count": None,
        "additional_metadata_present": None,
        "metadata_line_count": 0,
        "metadata_lines": [],
        "metadata_key_tokens": [],
        "cif_tag_tokens": [],
        "cif_tag_records": [],
        "cif_data_block_names": [],
        "source_radiation_probe": [],
        "source_radiation_probe_records": [],
        "source_wavelength": [],
        "source_wavelength_records": [],
        "source_two_theta_range_records": [],
        "source_intensity_loop_tags": [],
        "explicit_phase_block_count": 0,
        "phase_block_identifiers": [],
        "source_phase_names": [],
        "fullprof_style_evidence": [],
        "metadata_conflict": False,
        "metadata_conflict_notes": [],
    }
    if info.is_dir():
        record["content_read_status"] = "directory"
        return record

    try:
        raw = raw_override if raw_override is not None else archive.read(info)
        record["member_sha256"] = sha256_bytes(raw)
        record["content_read_status"] = "read"
        analysis_data = raw[:MAX_MEMBER_ANALYSIS_BYTES]
        record["analysis_truncated"] = len(raw) > len(analysis_data)
        text, encoding = decode_member_text(analysis_data)
        record["text_decode_encoding"] = encoding
        if text is None:
            record["diffraction_array_basis"] = "opaque_or_binary_member"
            return record

        record["text_preview"] = text[:MAX_TEXT_PREVIEW_CHARS]
        numeric = inspect_numeric_array(text)
        metadata = collect_text_metadata(text)
        fullprof = collect_fullprof_metadata(text)
        pattern = find_intensity_header_and_block(text)
        content_family = classify_content_family(
            text=text,
            metadata=metadata,
            fullprof=fullprof,
            pattern=pattern,
            numeric_summary=numeric,
        )
        arrays_present, basis = diffraction_status(
            text=text,
            pattern=pattern,
            numeric_summary=numeric,
        )

        phase_identifiers = list(
            dict.fromkeys(
                (metadata.get("phase_block_identifiers") or [])
                + (fullprof.get("fullprof_phase_block_identifiers") or [])
            )
        )
        phase_names = list(
            dict.fromkeys(
                (metadata.get("source_phase_names") or [])
                + (fullprof.get("fullprof_phase_names") or [])
            )
        )
        wavelength_records = list(
            (metadata.get("source_wavelength_records") or [])
            + (fullprof.get("fullprof_wavelength_records") or [])
        )
        source_radiation_probe = [
            unquote_source_value(record["raw_value_text"])
            for record in metadata.get("source_radiation_probe_records") or []
            if record.get("raw_value_text")
        ]
        source_wavelength = [
            unquote_source_value(record["raw_value_text"])
            for record in wavelength_records
            if record.get("raw_value_text")
        ]
        explicit_phase_block_count = max(
            len(phase_identifiers),
            len(phase_names),
        )
        metadata_conflict, metadata_conflict_notes = build_metadata_conflict(
            entry=entry or {},
            metadata=metadata,
            fullprof=fullprof,
            content_family=content_family,
        )
        record.update(
            {
                "numeric_array_present": numeric["numeric_array_present"],
                "numeric_row_count": numeric["numeric_row_count"],
                "numeric_value_count": numeric["numeric_value_count"],
                "numeric_column_counts": numeric["numeric_column_counts"],
                "dominant_numeric_column_count": numeric[
                    "dominant_numeric_column_count"
                ],
                "detected_content_family": content_family,
                "diffraction_array": arrays_present,
                "diffraction_arrays_present": arrays_present,
                "diffraction_array_basis": basis,
                "experimental_profile_parse_status": (
                    "candidate_safe_after_terminal_padding_review"
                    if (
                        arrays_present is True
                        and pattern.get("trailing_zero_padding_candidate")
                    )
                    else (
                        "safe_grid_consistent"
                        if arrays_present is True
                        else (
                            "not_safe_unknown_array_semantics"
                            if arrays_present is None
                            else "not_a_diffraction_profile"
                        )
                    )
                ),
                "header_found": pattern.get("header_found", False),
                "header_candidate_count": pattern.get(
                    "header_candidate_count",
                    0,
                ),
                "header_raw_text": pattern.get("header_raw_text"),
                "two_theta_start_raw": pattern.get("two_theta_start_raw"),
                "step_raw": pattern.get("step_raw"),
                "two_theta_end_raw": pattern.get("two_theta_end_raw"),
                "grid_alignment_exact": pattern.get("grid_alignment_exact"),
                "expected_point_count": pattern.get("expected_point_count"),
                "raw_numeric_value_count": pattern.get(
                    "raw_numeric_value_count"
                ),
                "observed_intensity_count": pattern.get(
                    "observed_intensity_count"
                ),
                "observed_intensity_count_excluding_trailing_zero_padding": (
                    pattern.get(
                        "observed_intensity_count_excluding_trailing_zero_padding"
                    )
                ),
                "trailing_zero_padding_count": pattern.get(
                    "trailing_zero_padding_count",
                    0,
                ),
                "trailing_zero_padding_candidate": pattern.get(
                    "trailing_zero_padding_candidate",
                    False,
                ),
                "fixed_width_padding_candidate": pattern.get(
                    "fixed_width_padding_candidate",
                    False,
                ),
                "trailing_zero_padding_review_reason": pattern.get(
                    "trailing_zero_padding_review_reason"
                ),
                "point_count_consistency": pattern.get(
                    "point_count_consistency"
                ),
                "point_count_review_reasons": pattern.get(
                    "point_count_review_reasons",
                    [],
                ),
                "data_line_count": pattern.get("data_line_count", 0),
                "data_column_counts": pattern.get("data_column_counts", {}),
                "dominant_data_column_count": pattern.get(
                    "dominant_data_column_count"
                ),
                "additional_metadata_present": metadata[
                    "additional_metadata_present"
                ],
                "metadata_line_count": metadata["metadata_line_count"],
                "metadata_lines": metadata["metadata_lines"],
                "metadata_key_tokens": metadata["metadata_key_tokens"],
                "cif_tag_tokens": metadata["cif_tag_tokens"],
                "cif_tag_records": metadata["cif_tag_records"],
                "cif_data_block_names": metadata["cif_data_block_names"],
                "source_radiation_probe": source_radiation_probe,
                "source_radiation_probe_records": metadata[
                    "source_radiation_probe_records"
                ],
                "source_wavelength": source_wavelength,
                "source_wavelength_records": wavelength_records,
                "source_two_theta_range_records": metadata[
                    "source_two_theta_range_records"
                ],
                "source_intensity_loop_tags": metadata[
                    "source_intensity_loop_tags"
                ],
                "explicit_phase_block_count": explicit_phase_block_count,
                "phase_block_identifiers": phase_identifiers,
                "source_phase_names": phase_names,
                "fullprof_style_evidence": fullprof[
                    "fullprof_style_evidence"
                ],
                "metadata_conflict": metadata_conflict,
                "metadata_conflict_notes": metadata_conflict_notes,
            }
        )
    except Exception as exc:
        record["content_read_status"] = "error"
        record["content_read_error"] = f"{type(exc).__name__}: {exc}"
    return record


def inspect_archive(path: Path, entry: dict[str, Any]) -> dict[str, Any]:
    record: dict[str, Any] = {
        "entry_id": entry["entry_id"],
        "zip_url": entry["zip_url"],
        "zip_path": str(path.resolve()),
        "zip_exists": path.is_file(),
        "zip_size_bytes": path.stat().st_size if path.is_file() else 0,
        "zip_sha256": sha256_file(path) if path.is_file() else None,
        "source_filename": path.name,
        "source_size_bytes": path.stat().st_size if path.is_file() else 0,
        "source_sha256": sha256_file(path) if path.is_file() else None,
        "original_filename": path.name,
        "original_sha256": sha256_file(path) if path.is_file() else None,
        "archive_open_status": "not_opened",
        "archive_container_type": "unknown",
        "archive_content_status": "not_inspected",
        "archive_usable_for_audit": False,
        "payload_read_status": "not_read",
        "payload_filename": None,
        "payload_record": None,
        "archive_error": None,
        "source_extension": None,
        "two_theta_start_raw": None,
        "step_raw": None,
        "two_theta_end_raw": None,
        "experimental_profile_parse_status": "not_assessed",
        "detected_content_family": "unknown",
        "diffraction_array": None,
        "expected_point_count": None,
        "grid_alignment_exact": None,
        "observed_intensity_count": None,
        "observed_intensity_count_excluding_trailing_zero_padding": None,
        "raw_numeric_value_count": None,
        "trailing_zero_padding_count": 0,
        "trailing_zero_padding_candidate": False,
        "fixed_width_padding_candidate": False,
        "trailing_zero_padding_review_reason": None,
        "point_count_consistency": None,
        "point_count_review_reasons": [],
        "explicit_phase_block_count": 0,
        "source_phase_names": [],
        "source_radiation_probe": [],
        "source_wavelength": [],
        "source_intensity_loop_tags": [],
        "metadata_conflict": False,
        "metadata_conflict_notes": [],
        "contained_filenames": [],
        "contained_extensions": [],
        "cif_files": [],
        "dat_files": [],
        "other_files": [],
        "member_count": 0,
        "analyzed_content_record_count": 0,
        "members": [],
        "numeric_array_member_count": 0,
        "diffraction_array_member_count": 0,
        "diffraction_array_unknown_member_count": 0,
        "additional_metadata_member_count": 0,
    }
    if not path.is_file():
        record["archive_open_status"] = "missing"
        return record

    try:
        with zipfile.ZipFile(path) as archive:
            bad_member = archive.testzip()
            infos = archive.infolist()
            members = [
                inspect_member(archive, info, entry=entry)
                for info in infos
            ]
            filenames = [member["member_filename"] for member in members]
            extensions = sorted(
                {
                    member["extension_lower"]
                    for member in members
                    if member["extension_lower"]
                }
            )
            cif_files = [
                member["member_filename"]
                for member in members
                if member["extension_lower"] == ".cif"
            ]
            dat_files = [
                member["member_filename"]
                for member in members
                if member["extension_lower"] == ".dat"
            ]
            known_files = set(cif_files) | set(dat_files)
            other_files = [
                member["member_filename"]
                for member in members
                if member["member_filename"] not in known_files
                and not member["is_directory"]
            ]
            content_members = [
                member for member in members if not member["is_directory"]
            ]
            primary_member = (
                content_members[0] if len(content_members) == 1 else None
            )
            record.update(
                {
                    "archive_open_status": "ok" if bad_member is None else "crc_error",
                    "archive_container_type": "zip",
                    "archive_content_status": (
                        "zip_archive" if bad_member is None else "zip_crc_error"
                    ),
                    "archive_usable_for_audit": True,
                    "payload_read_status": "zip_members_read",
                    "archive_bad_member": bad_member,
                    "contained_filenames": filenames,
                    "contained_extensions": extensions,
                    "cif_files": cif_files,
                    "dat_files": dat_files,
                    "other_files": other_files,
                    "member_count": len(members),
                    "analyzed_content_record_count": len(content_members),
                    "members": members,
                    "source_extension": (
                        primary_member["source_extension"]
                        if primary_member
                        else None
                    ),
                    "two_theta_start_raw": (
                        primary_member["two_theta_start_raw"]
                        if primary_member
                        else None
                    ),
                    "step_raw": (
                        primary_member["step_raw"]
                        if primary_member
                        else None
                    ),
                    "two_theta_end_raw": (
                        primary_member["two_theta_end_raw"]
                        if primary_member
                        else None
                    ),
                    "detected_content_family": (
                        primary_member["detected_content_family"]
                        if primary_member
                        else "mixed"
                    ),
                    "diffraction_array": (
                        primary_member["diffraction_array"]
                        if primary_member
                        else None
                    ),
                    "experimental_profile_parse_status": (
                        primary_member["experimental_profile_parse_status"]
                        if primary_member
                        else "not_assessed"
                    ),
                    "expected_point_count": (
                        primary_member["expected_point_count"]
                        if primary_member
                        else None
                    ),
                    "grid_alignment_exact": (
                        primary_member["grid_alignment_exact"]
                        if primary_member
                        else None
                    ),
                    "observed_intensity_count": (
                        primary_member["observed_intensity_count"]
                        if primary_member
                        else None
                    ),
                    "observed_intensity_count_excluding_trailing_zero_padding": (
                        primary_member[
                            "observed_intensity_count_excluding_trailing_zero_padding"
                        ]
                        if primary_member
                        else None
                    ),
                    "raw_numeric_value_count": (
                        primary_member["raw_numeric_value_count"]
                        if primary_member
                        else None
                    ),
                    "trailing_zero_padding_count": (
                        primary_member["trailing_zero_padding_count"]
                        if primary_member
                        else 0
                    ),
                    "trailing_zero_padding_candidate": (
                        primary_member["trailing_zero_padding_candidate"]
                        if primary_member
                        else False
                    ),
                    "fixed_width_padding_candidate": (
                        primary_member["fixed_width_padding_candidate"]
                        if primary_member
                        else False
                    ),
                    "trailing_zero_padding_review_reason": (
                        primary_member["trailing_zero_padding_review_reason"]
                        if primary_member
                        else None
                    ),
                    "point_count_consistency": (
                        primary_member["point_count_consistency"]
                        if primary_member
                        else None
                    ),
                    "point_count_review_reasons": (
                        primary_member["point_count_review_reasons"]
                        if primary_member
                        else []
                    ),
                    "explicit_phase_block_count": (
                        primary_member["explicit_phase_block_count"]
                        if primary_member
                        else 0
                    ),
                    "source_phase_names": (
                        primary_member["source_phase_names"]
                        if primary_member
                        else []
                    ),
                    "source_radiation_probe": (
                        primary_member["source_radiation_probe"]
                        if primary_member
                        else []
                    ),
                    "source_wavelength": (
                        primary_member["source_wavelength"]
                        if primary_member
                        else []
                    ),
                    "source_intensity_loop_tags": (
                        primary_member["source_intensity_loop_tags"]
                        if primary_member
                        else []
                    ),
                    "metadata_conflict": (
                        primary_member["metadata_conflict"]
                        if primary_member
                        else False
                    ),
                    "metadata_conflict_notes": (
                        primary_member["metadata_conflict_notes"]
                        if primary_member
                        else []
                    ),
                    "numeric_array_member_count": sum(
                        member["numeric_array_present"] is True
                        for member in members
                    ),
                    "diffraction_array_member_count": sum(
                        member["diffraction_array"] is True
                        for member in members
                    ),
                    "diffraction_array_unknown_member_count": sum(
                        member["diffraction_array"] is None
                        for member in members
                        if not member["is_directory"]
                    ),
                    "additional_metadata_member_count": sum(
                        member["additional_metadata_present"] is True
                        for member in members
                    ),
                }
            )
    except zipfile.BadZipFile as exc:
        raw = path.read_bytes()
        synthetic_info = SimpleNamespace(
            filename=path.name,
            is_dir=lambda: False,
            file_size=len(raw),
            compress_size=0,
            CRC=binascii.crc32(raw) & 0xFFFFFFFF,
        )
        payload = inspect_member(
            None,
            synthetic_info,
            entry=entry,
            raw_override=raw,
        )
        supported_text_family = payload.get("detected_content_family") in {
            "legacy_intensity_array",
            "fullprof_style_pattern",
            "commented_pdcif",
        }
        record.update(
            {
                "archive_open_status": "not_zip_readable_text",
                "archive_container_type": "plain_text",
                "archive_content_status": (
                    "readable_text_supported_diffraction"
                    if supported_text_family
                    else "readable_text"
                ),
                "archive_usable_for_audit": True,
                "payload_read_status": "readable_text",
                "payload_filename": path.name,
                "payload_record": payload,
                "archive_error": (
                    f"{type(exc).__name__}: {exc}; "
                    "retained and inspected as readable text"
                ),
                "analyzed_content_record_count": 1,
                "source_extension": payload["source_extension"],
                "detected_content_family": payload[
                    "detected_content_family"
                ],
                "diffraction_array": payload["diffraction_array"],
                "experimental_profile_parse_status": payload[
                    "experimental_profile_parse_status"
                ],
                "two_theta_start_raw": payload["two_theta_start_raw"],
                "step_raw": payload["step_raw"],
                "two_theta_end_raw": payload["two_theta_end_raw"],
                "expected_point_count": payload["expected_point_count"],
                "grid_alignment_exact": payload["grid_alignment_exact"],
                "observed_intensity_count": payload[
                    "observed_intensity_count"
                ],
                "observed_intensity_count_excluding_trailing_zero_padding": (
                    payload[
                        "observed_intensity_count_excluding_trailing_zero_padding"
                    ]
                ),
                "raw_numeric_value_count": payload[
                    "raw_numeric_value_count"
                ],
                "trailing_zero_padding_count": payload[
                    "trailing_zero_padding_count"
                ],
                "trailing_zero_padding_candidate": payload[
                    "trailing_zero_padding_candidate"
                ],
                "fixed_width_padding_candidate": payload[
                    "fixed_width_padding_candidate"
                ],
                "trailing_zero_padding_review_reason": payload[
                    "trailing_zero_padding_review_reason"
                ],
                "point_count_consistency": payload[
                    "point_count_consistency"
                ],
                "point_count_review_reasons": payload[
                    "point_count_review_reasons"
                ],
                "explicit_phase_block_count": payload[
                    "explicit_phase_block_count"
                ],
                "source_phase_names": payload["source_phase_names"],
                "source_radiation_probe": payload[
                    "source_radiation_probe"
                ],
                "source_wavelength": payload["source_wavelength"],
                "source_intensity_loop_tags": payload[
                    "source_intensity_loop_tags"
                ],
                "metadata_conflict": payload["metadata_conflict"],
                "metadata_conflict_notes": payload[
                    "metadata_conflict_notes"
                ],
                "numeric_array_member_count": int(
                    payload["numeric_array_present"] is True
                ),
                "diffraction_array_member_count": int(
                    payload["diffraction_array"] is True
                ),
                "diffraction_array_unknown_member_count": int(
                    payload["diffraction_array"] is None
                ),
                "additional_metadata_member_count": int(
                    payload["additional_metadata_present"] is True
                ),
            }
        )
    except Exception as exc:
        record["archive_open_status"] = "error"
        record["archive_error"] = f"{type(exc).__name__}: {exc}"
    return record


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part_path = path.with_name(path.name + ".part")
    with part_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    os.replace(part_path, path)


def flatten_index_record(record: dict[str, Any]) -> dict[str, Any]:
    flattened = dict(record)
    for key in (
        "zip_links_on_same_line",
        "raw_hash_delimited_tokens",
        "optional_gif_links",
        "optional_wrl_links",
        "all_raw_links",
    ):
        flattened[key] = json.dumps(
            record.get(key, []),
            ensure_ascii=False,
        )
    # The base64 field is intentionally retained in the CSV too: it permits
    # exact byte recovery even if a spreadsheet changes text encoding.
    return flattened


INDEX_CSV_FIELDS = [
    "line_number",
    "entry_id",
    "zip_url",
    "zip_raw_href",
    "raw_index_text",
    "raw_index_text_without_line_ending",
    "raw_index_bytes_base64",
    "raw_index_text_encoding",
    "raw_line_ending",
    "apparent_formula_name_token",
    "apparent_formula_name_token_source",
    "raw_hash_delimited_tokens",
    "raw_hash_delimited_token_count",
    "raw_bibliographic_comment_text",
    "raw_visible_text",
    "optional_gif_links",
    "optional_wrl_links",
    "all_raw_links",
]


def write_index_csv(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part_path = path.with_name(path.name + ".part")
    with part_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=INDEX_CSV_FIELDS,
            extrasaction="ignore",
        )
        writer.writeheader()
        for record in records:
            writer.writerow(flatten_index_record(record))
    os.replace(part_path, path)


def tri_state_text(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "unknown"


def compact_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


PILOT_REPORT_FIELDS = [
    "entry_id",
    "apparent_formula_name_token",
    "index_raw_hash_delimited_tokens",
    "zip_url",
    "source_filename",
    "source_sha256",
    "archive_container_type",
    "archive_open_status",
    "archive_content_status",
    "archive_usable_for_audit",
    "payload_filename",
    "source_extension",
    "detected_content_family",
    "diffraction_array",
    "experimental_profile_parse_status",
    "two_theta_start_raw",
    "step_raw",
    "two_theta_end_raw",
    "expected_point_count",
    "raw_numeric_value_count",
    "observed_intensity_count",
    "observed_intensity_count_excluding_trailing_zero_padding",
    "trailing_zero_padding_count",
    "trailing_zero_padding_candidate",
    "fixed_width_padding_candidate",
    "trailing_zero_padding_review_reason",
    "point_count_consistency",
    "point_count_review_reasons",
    "explicit_phase_block_count",
    "source_phase_names",
    "source_radiation_probe",
    "source_wavelength",
    "source_intensity_loop_tags",
    "metadata_conflict",
    "metadata_conflict_notes",
]


def build_pilot_rows(
    index_records: list[dict[str, Any]],
    archive_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    index_by_id = {
        record["entry_id"]: record
        for record in index_records
    }
    rows: list[dict[str, Any]] = []
    for archive in archive_records:
        entry = index_by_id.get(archive["entry_id"], {})
        row = {
            "entry_id": archive["entry_id"],
            "apparent_formula_name_token": entry.get(
                "apparent_formula_name_token"
            ),
            "index_raw_hash_delimited_tokens": entry.get(
                "raw_hash_delimited_tokens"
            )
            or [],
            "zip_url": archive.get("zip_url"),
            "source_filename": archive.get("source_filename"),
            "source_sha256": archive.get("source_sha256"),
            "archive_container_type": archive.get(
                "archive_container_type"
            ),
            "archive_open_status": archive.get("archive_open_status"),
            "archive_content_status": archive.get(
                "archive_content_status"
            ),
            "archive_usable_for_audit": archive.get(
                "archive_usable_for_audit"
            ),
            "payload_filename": archive.get("payload_filename"),
            "source_extension": archive.get("source_extension"),
            "detected_content_family": archive.get(
                "detected_content_family"
            ),
            "diffraction_array": tri_state_text(
                archive.get("diffraction_array")
            ),
            "experimental_profile_parse_status": archive.get(
                "experimental_profile_parse_status"
            ),
            "two_theta_start_raw": archive.get("two_theta_start_raw"),
            "step_raw": archive.get("step_raw"),
            "two_theta_end_raw": archive.get("two_theta_end_raw"),
            "expected_point_count": archive.get("expected_point_count"),
            "raw_numeric_value_count": archive.get(
                "raw_numeric_value_count"
            ),
            "observed_intensity_count": archive.get(
                "observed_intensity_count"
            ),
            "observed_intensity_count_excluding_trailing_zero_padding": (
                archive.get(
                    "observed_intensity_count_excluding_trailing_zero_padding"
                )
            ),
            "trailing_zero_padding_count": archive.get(
                "trailing_zero_padding_count"
            ),
            "trailing_zero_padding_candidate": archive.get(
                "trailing_zero_padding_candidate"
            ),
            "fixed_width_padding_candidate": archive.get(
                "fixed_width_padding_candidate"
            ),
            "trailing_zero_padding_review_reason": archive.get(
                "trailing_zero_padding_review_reason"
            ),
            "point_count_consistency": tri_state_text(
                archive.get("point_count_consistency")
            ),
            "point_count_review_reasons": archive.get(
                "point_count_review_reasons"
            )
            or [],
            "explicit_phase_block_count": archive.get(
                "explicit_phase_block_count",
                0,
            ),
            "source_phase_names": archive.get("source_phase_names") or [],
            "source_radiation_probe": archive.get(
                "source_radiation_probe"
            )
            or [],
            "source_wavelength": archive.get("source_wavelength") or [],
            "source_intensity_loop_tags": archive.get(
                "source_intensity_loop_tags"
            )
            or [],
            "metadata_conflict": bool(
                archive.get("metadata_conflict", False)
            ),
            "metadata_conflict_notes": archive.get(
                "metadata_conflict_notes"
            )
            or [],
        }
        rows.append(row)
    return rows


def write_pilot_report(
    inventory_root: Path,
    rows: list[dict[str, Any]],
) -> dict[str, str]:
    jsonl_path = inventory_root / "powbase_pilot_report.jsonl"
    csv_path = inventory_root / "powbase_pilot_report.csv"
    markdown_path = inventory_root / "powbase_pilot_report.md"

    write_jsonl(jsonl_path, rows)

    part_path = csv_path.with_name(csv_path.name + ".part")
    with part_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=PILOT_REPORT_FIELDS,
            extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            flattened = dict(row)
            for field in (
                "point_count_review_reasons",
                "index_raw_hash_delimited_tokens",
                "source_phase_names",
                "source_radiation_probe",
                "source_wavelength",
                "source_intensity_loop_tags",
                "metadata_conflict_notes",
            ):
                flattened[field] = compact_json(row.get(field) or [])
            writer.writerow(flattened)
    os.replace(part_path, csv_path)

    lines = [
        "# PowBase Six-Record Pilot Audit",
        "",
        "This report contains audit evidence only. It does not promote "
        "phase blocks to canonical multi-phase metadata and does not modify "
        "source scientific values.",
        "",
        "| Entry | Array | Content family | Expected | Observed | Raw | Pad | Consistent | Phases | Radiation | Wavelength | Conflict |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- | ---: | --- | --- | --- |",
    ]
    for row in rows:
        radiation = ", ".join(row["source_radiation_probe"]) or "not recovered"
        wavelength = ", ".join(row["source_wavelength"]) or "not recovered"
        lines.append(
            "| {entry_id} | {diffraction_array} | {detected_content_family} | "
                "{expected_point_count} | {observed_intensity_count} | "
                "{raw_numeric_value_count} | {trailing_zero_padding_count} | "
                "{point_count_consistency} | {explicit_phase_block_count} | "
                "{radiation} | {wavelength} | {metadata_conflict} |".format(
                **row,
                radiation=radiation,
                wavelength=wavelength,
            )
        )
    lines.extend(
        [
            "",
            "The JSONL and CSV files retain review reasons, phase names, "
            "source metadata values, index raw tokens, and conflict notes in "
            "full. Observed intensity counts are literal counts from the "
            "source data block; any count excluding terminal zeros is kept "
            "as a separate padding candidate field. Source bytes and "
            "intensity values are unchanged.",
        ]
    )
    write_text_atomic(markdown_path, "\n".join(lines))
    return {
        "jsonl": str(jsonl_path.resolve()),
        "csv": str(csv_path.resolve()),
        "markdown": str(markdown_path.resolve()),
    }


def write_markdown_report(
    path: Path,
    *,
    manifest: dict[str, Any],
    index_records: list[dict[str, Any]],
    archive_records: list[dict[str, Any]],
) -> None:
    index_summary = manifest["index_summary"]
    archive_summary = manifest["archive_summary"]
    family_counts_text = json.dumps(
        archive_summary["detected_content_family_counts"],
        ensure_ascii=False,
        sort_keys=True,
    )
    lines = [
        "# PowBase Audit",
        "",
        f"- Audit timestamp (UTC): `{manifest['audit_timestamp_utc']}`",
        f"- Official index URL: `{manifest['index_url']}`",
        f"- Index SHA-256: `{index_summary['source_sha256']}`",
        f"- Index entries parsed: `{index_summary['index_entry_count']}`",
        f"- Unique entry IDs: `{index_summary['unique_entry_id_count']}`",
        "",
        "This is an inventory only. No MongoDB writes or canonical CrystalDB "
        "ingestion were performed.",
        "",
        "## Archive Counts",
        "",
        f"- Downloaded or already present: `{archive_summary['available_archive_count']}`",
        f"- Missing or download failed: `{archive_summary['unavailable_archive_count']}`",
        f"- ZIPs opened successfully: `{archive_summary['archive_open_ok_count']}`",
        f"- Readable non-ZIP text payloads: "
        f"`{archive_summary['non_zip_readable_text_count']}`",
        f"- Sources usable for audit: "
        f"`{archive_summary['archive_usable_for_audit_count']}`",
        f"- ZIPs with CIF members: `{archive_summary['archives_with_cif_count']}`",
        f"- ZIPs with DAT members: `{archive_summary['archives_with_dat_count']}`",
        f"- ZIPs with other members: `{archive_summary['archives_with_other_count']}`",
        f"- ZIPs with at least one numeric array: `{archive_summary['archives_with_numeric_array_count']}`",
        f"- ZIPs with supported diffraction-array evidence: "
        f"`{archive_summary['archives_with_diffraction_array_count']}`",
        f"- Diffraction array true/false/unknown: "
        f"`{archive_summary['diffraction_array_true_count']}/"
        f"{archive_summary['diffraction_array_false_count']}/"
        f"{archive_summary['diffraction_array_unknown_count']}`",
        f"- Detected content families: `{family_counts_text}`",
        f"- Metadata conflicts: `{archive_summary['metadata_conflict_count']}`",
        "",
        "## Entry-Level Notes",
        "",
        "The JSONL inventory preserves the complete raw index string, its "
        "base64 byte representation, every raw `#` token, and the ZIP member "
        "inventory. Formula/name values are only populated when a visibly "
        "separable token was available; no radiation, wavelength, phase "
        "purity, formula confirmation, or structure linkage is inferred.",
        "",
    ]
    failed = [
        record
        for record in archive_records
        if record.get("archive_open_status")
        not in {"ok", "crc_error", "not_zip_readable_text"}
    ]
    if failed:
        lines.extend(
            [
                "## Archive Failures",
                "",
                "| Entry ID | Status | Error |",
                "| --- | --- | --- |",
            ]
        )
        for record in failed:
            lines.append(
                f"| {record['entry_id']} | {record['archive_open_status']} | "
                f"{record.get('archive_error') or ''} |"
            )
        lines.append("")

    write_text_atomic(path, "\n".join(lines))


def ensure_safe_output_root(output_root: Path) -> None:
    resolved = output_root.resolve()
    lowered = str(resolved).casefold().replace("\\", "/")
    if "canonical" in lowered or "/production" in lowered or "mongodb" in lowered:
        raise ValueError(
            f"refusing to write audit output below a production/canonical path: {resolved}"
        )
    if "powbase" not in resolved.name.casefold():
        raise ValueError(
            "audit output directory must be explicitly named for PowBase: "
            f"{resolved}"
        )


def build_archive_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "archive_record_count": len(records),
        "available_archive_count": sum(
            record["zip_exists"] for record in records
        ),
        "unavailable_archive_count": sum(
            not record["zip_exists"] for record in records
        ),
        "archive_open_ok_count": sum(
            record["archive_open_status"] == "ok" for record in records
        ),
        "non_zip_readable_text_count": sum(
            record["archive_open_status"] == "not_zip_readable_text"
            for record in records
        ),
        "archive_usable_for_audit_count": sum(
            bool(record.get("archive_usable_for_audit"))
            for record in records
        ),
        "archive_open_error_count": sum(
            record["archive_open_status"] == "error" for record in records
        ),
        "archives_with_cif_count": sum(
            bool(record["cif_files"]) for record in records
        ),
        "archives_with_dat_count": sum(
            bool(record["dat_files"]) for record in records
        ),
        "archives_with_other_count": sum(
            bool(record["other_files"]) for record in records
        ),
        "archives_with_numeric_array_count": sum(
            record["numeric_array_member_count"] > 0 for record in records
        ),
        "archives_with_diffraction_array_count": sum(
            record["diffraction_array_member_count"] > 0
            for record in records
        ),
        "archives_with_unknown_array_semantics_count": sum(
            record["diffraction_array_unknown_member_count"] > 0
            for record in records
        ),
        "detected_content_family_counts": dict(
            Counter(
                record.get("detected_content_family", "unknown")
                for record in records
            )
        ),
        "diffraction_array_true_count": sum(
            record.get("diffraction_array") is True
            for record in records
        ),
        "diffraction_array_false_count": sum(
            record.get("diffraction_array") is False
            for record in records
        ),
        "diffraction_array_unknown_count": sum(
            record.get("diffraction_array") is None
            for record in records
        ),
        "metadata_conflict_count": sum(
            bool(record.get("metadata_conflict"))
            for record in records
        ),
    }


def run_audit(args: argparse.Namespace) -> dict[str, Any]:
    output_root = args.output_root.resolve()
    ensure_safe_output_root(output_root)
    raw_root = output_root / "raw"
    archive_root = output_root / "archives"
    inventory_root = output_root / "inventory"
    raw_root.mkdir(parents=True, exist_ok=True)
    archive_root.mkdir(parents=True, exist_ok=True)
    inventory_root.mkdir(parents=True, exist_ok=True)

    index_path = (
        args.index_path.resolve()
        if args.index_path is not None
        else (raw_root / "powbase.txt").resolve()
    )

    session = build_session(args.max_retries)
    if args.index_path is not None:
        if not index_path.is_file():
            raise FileNotFoundError(f"local index does not exist: {index_path}")
        index_download = {
            "status": "local_input",
            "source_kind": "local_index",
            "url": args.index_url,
            "path": str(index_path),
            "size_bytes": index_path.stat().st_size,
            "sha256": sha256_file(index_path),
        }
    elif args.no_download_index and index_path.is_file():
        index_download = {
            "status": "existing_local_index",
            "source_kind": "existing_local_index",
            "url": args.index_url,
            "path": str(index_path),
            "size_bytes": index_path.stat().st_size,
            "sha256": sha256_file(index_path),
        }
    else:
        index_download = download_index(
            session,
            args.index_url,
            index_path,
            args.timeout,
        )
        if index_download["status"] == "error":
            raise RuntimeError(
                f"unable to fetch official PowBase index: {index_download['error']}"
            )

    index_bytes = index_path.read_bytes()
    index_records, index_summary = parse_index_bytes(index_bytes, args.index_url)
    if args.entry_ids:
        selected_ids = set(args.entry_ids)
        index_records = [
            record for record in index_records if record["entry_id"] in selected_ids
        ]
    if args.limit is not None:
        index_records = index_records[: args.limit]

    # Keep the first record for each ID as the download target.  Duplicate
    # source lines remain in the index inventory and are reported separately.
    unique_entries: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for record in index_records:
        if record["entry_id"] not in seen_ids:
            unique_entries.append(record)
            seen_ids.add(record["entry_id"])

    archive_records: list[dict[str, Any]] = []
    for position, entry in enumerate(unique_entries, start=1):
        filename = sanitize_filename(entry["entry_id"]) + ".zip"
        archive_path = archive_root / filename
        download_result = download_bytes(
            session,
            entry["zip_url"],
            archive_path,
            args.timeout,
        )
        archive_record = inspect_archive(archive_path, entry)
        archive_record["download"] = download_result
        archive_record["download_sequence"] = position
        archive_records.append(archive_record)
        print(
            f"[{position}/{len(unique_entries)}] {entry['entry_id']} "
            f"{download_result['status']} "
            f"{archive_record['archive_open_status']}",
            flush=True,
        )

    archive_summary = build_archive_summary(archive_records)
    pilot_report_paths = None
    if args.entry_ids:
        pilot_report_paths = write_pilot_report(
            inventory_root,
            build_pilot_rows(index_records, archive_records),
        )
    manifest = {
        "audit_version": "powbase-audit-v2",
        "audit_timestamp_utc": utc_now(),
        "source": "PowBase official legacy index",
        "index_url": args.index_url,
        "index_path": str(index_path),
        "index_download": index_download,
        "index_summary": index_summary,
        "selection": {
            "entry_ids": args.entry_ids,
            "limit": args.limit,
            "selected_source_record_count": len(index_records),
            "unique_archive_count": len(unique_entries),
        },
        "archive_summary": archive_summary,
        "pilot_report_paths": pilot_report_paths,
        "constraints": {
            "mongodb_writes": False,
            "canonical_ingestion": False,
            "production_release_modified": False,
            "fixed_metadata_schema_assumed": False,
            "radiation_or_wavelength_inferred": False,
            "formula_confirmed": False,
            "structure_linkage_inferred": False,
        },
        "output_root": str(output_root),
    }

    write_jsonl(
        inventory_root / "powbase_index_inventory.jsonl",
        index_records,
    )
    write_jsonl(
        inventory_root / "powbase_archive_inventory.jsonl",
        archive_records,
    )
    write_index_csv(inventory_root / "powbase_entry_inventory.csv", index_records)
    write_json_atomic(output_root / "powbase_audit_manifest.json", manifest)
    write_markdown_report(
        output_root / "powbase_audit_report.md",
        manifest=manifest,
        index_records=index_records,
        archive_records=archive_records,
    )
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit the official PowBase index and individual ZIP archives."
    )
    parser.add_argument("--index-url", default=DEFAULT_INDEX_URL)
    parser.add_argument(
        "--index-path",
        type=Path,
        help="Use an existing local powbase.txt and do not download the index.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
    )
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument(
        "--no-download-index",
        action="store_true",
        help="Reuse <output-root>/raw/powbase.txt if it already exists.",
    )
    parser.add_argument(
        "--entry-ids",
        nargs="+",
        help="Audit only these entry IDs after parsing the complete index.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Audit at most this many parsed source entries.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.timeout <= 0:
        raise SystemExit("--timeout must be > 0")
    if args.max_retries < 0:
        raise SystemExit("--max-retries must be >= 0")
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be >= 1")

    try:
        manifest = run_audit(args)
    except Exception as exc:
        print(f"FATAL: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(manifest["archive_summary"], indent=2, ensure_ascii=False))
    print(f"Index inventory: {args.output_root / 'inventory' / 'powbase_index_inventory.jsonl'}")
    print(f"Archive inventory: {args.output_root / 'inventory' / 'powbase_archive_inventory.jsonl'}")
    if manifest.get("pilot_report_paths"):
        print(
            "Pilot report: "
            + manifest["pilot_report_paths"]["markdown"]
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
