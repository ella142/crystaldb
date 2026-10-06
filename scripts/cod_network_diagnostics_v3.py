"""Diagnose COD connectivity and validate the existing Python client path."""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import gemmi
import requests

from crystaldb.sources.cod import COD_CIF_URL, COD_SEARCH_URL
from crystaldb.sources.cod.single_crystal_parser import parse_cod_cif


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = Path(r"D:\document\aiformaterials\rruff\cif_recovery_v3")
REPORT_PATH = OUTPUT_ROOT / "reports" / "cod_network_diagnostics_v3.md"


def _safe_proxy(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r"(://)([^:/@]+):([^@]+)@", r"\1***:***@", value)


def _run_command(command: list[str]) -> str:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        return (completed.stdout + completed.stderr).strip()
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def _dns(host: str) -> dict:
    try:
        name, aliases, addresses = socket.gethostbyname_ex(host)
        return {
            "status": "ok",
            "name": name,
            "aliases": aliases,
            "addresses": addresses,
        }
    except Exception as exc:
        return {
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
        }


def _tcp(host: str, port: int) -> dict:
    try:
        with socket.create_connection((host, port), timeout=10) as connection:
            return {
                "status": "ok",
                "peer": connection.getpeername(),
            }
    except Exception as exc:
        return {
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
        }


def _request_check(session: requests.Session) -> dict:
    result = {
        "trust_env": session.trust_env,
        "proxies": {
            key: _safe_proxy(value)
            for key, value in session.proxies.items()
        },
    }
    try:
        response = session.get(
            COD_SEARCH_URL,
            params={"text": "Beryl", "format": "lst"},
            timeout=(10, 30),
        )
        body = response.text
        ids = [
            line.strip()
            for line in body.splitlines()
            if line.strip().isdigit()
        ]
        result.update(
            {
                "status": "ok",
                "http_status": response.status_code,
                "url": response.url,
                "content_type": response.headers.get("content-type"),
                "content_length": len(response.content),
                "html_error": "<html" in body[:1000].lower(),
                "cod_id_count": len(ids),
                "sample_cod_ids": ids[:5],
            }
        )
        return result
    except Exception as exc:
        result.update(
            {
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        return result


def _cif_check(session: requests.Session, cod_id: str) -> dict:
    url = COD_CIF_URL.format(cod_id=cod_id)
    result = {"cod_id": cod_id, "url": url}
    try:
        response = session.get(url, timeout=(10, 45))
        text = response.text
        result.update(
            {
                "http_status": response.status_code,
                "content_type": response.headers.get("content-type"),
                "content_length": len(response.content),
                "html_error": "<html" in text[:2000].lower(),
                "has_data_block": bool(re.search(r"(?m)^\s*data_\S+", text)),
            }
        )
        with tempfile.TemporaryDirectory(prefix="cod_network_v3_") as temp_dir:
            path = Path(temp_dir) / f"{cod_id}.cif"
            path.write_text(text, encoding="utf-8")
            parsed = parse_cod_cif(path, source_id=cod_id)
        result.update(
            {
                "status": "ok",
                "parse_status": parsed.get("parse_status"),
                "formula": parsed.get("formula"),
                "space_group": parsed.get("space_group"),
                "atom_count": parsed.get("atom_count"),
            }
        )
        return result
    except Exception as exc:
        result.update(
            {
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        return result


def run() -> dict:
    host = "www.crystallography.net"
    env_proxy_names = (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "NO_PROXY",
        "no_proxy",
    )
    env_proxies = {
        name: _safe_proxy(os.environ.get(name))
        for name in env_proxy_names
        if os.environ.get(name)
    }

    default_session = requests.Session()
    no_env_session = requests.Session()
    no_env_session.trust_env = False
    default_query = _request_check(default_session)
    no_env_query = _request_check(no_env_session)

    known_session_name = None
    known_id = None
    for session_name, query in (
        ("default_trust_env", default_query),
        ("trust_env_false", no_env_query),
    ):
        for value in query.get("sample_cod_ids") or []:
            if value.isdigit():
                known_id = value
                known_session_name = session_name
                break
        if known_id:
            break
    known_session = (
        default_session
        if known_session_name == "default_trust_env"
        else no_env_session
    )
    cif_check = _cif_check(known_session, known_id) if known_id else {
        "status": "not_run",
        "reason": "known mineral query returned no COD IDs",
    }

    diagnostics = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "conda_default_env": os.environ.get("CONDA_DEFAULT_ENV"),
        "conda_prefix": os.environ.get("CONDA_PREFIX"),
        "gemmi_version": gemmi.__version__,
        "requests_version": requests.__version__,
        "dns": _dns(host),
        "direct_tcp_443": _tcp(host, 443),
        "proxy_environment": env_proxies,
        "requests_environ_proxies": {
            key: _safe_proxy(value)
            for key, value in requests.utils.get_environ_proxies(
                COD_SEARCH_URL
            ).items()
        },
        "winhttp_proxy": _run_command(["netsh", "winhttp", "show", "proxy"]),
        "default_session_query": default_query,
        "trust_env_false_query": no_env_query,
        "known_cif_check": cif_check,
        "known_cif_session": known_session_name,
        "old_client_audit": {
            "scripts_test_cod_search": (
                "requests.Session + HTTPAdapter/urllib3 Retry; "
                "default trust_env; session.get"
            ),
            "sources_cod_client": (
                "requests.get + manual retry/backoff; default trust_env"
            ),
            "v3_client": (
                "uses sources.cod.search_cod_targeted; "
                "same COD endpoint with a reusable session; current v3 "
                "run selects the verified direct trust_env=False path"
            ),
        },
    }

    query_ok = any(
        query.get("status") == "ok"
        and query.get("http_status") == 200
        and not query.get("html_error")
        and query.get("cod_id_count", 0) > 0
        for query in (default_query, no_env_query)
    )
    cod_online = (
        query_ok
        and cif_check.get("status") == "ok"
        and cif_check.get("http_status") == 200
        and cif_check.get("has_data_block")
        and cif_check.get("parse_status") in {"ok", "partial"}
    )
    diagnostics["COD_ONLINE"] = bool(cod_online)

    lines = [
        "# COD Network Diagnostics v3",
        "",
        f"- generated_at: `{diagnostics['generated_at']}`",
        f"- `COD_ONLINE`: **{'TRUE' if cod_online else 'FALSE'}**",
        "",
        "## Runtime",
        "",
        f"- Python executable: `{sys.executable}`",
        f"- Python version: `{sys.version.splitlines()[0]}`",
        f"- CONDA_DEFAULT_ENV: `{diagnostics['conda_default_env']}`",
        f"- CONDA_PREFIX: `{diagnostics['conda_prefix']}`",
        f"- Gemmi: `{gemmi.__version__}`",
        f"- requests: `{requests.__version__}`",
        "",
        "## Connectivity",
        "",
        f"- DNS: `{diagnostics['dns']}`",
        f"- direct TCP 443: `{diagnostics['direct_tcp_443']}`",
        f"- WinHTTP proxy: `{diagnostics['winhttp_proxy']}`",
        f"- proxy environment: `{env_proxies}`",
        f"- requests environment proxies: `{diagnostics['requests_environ_proxies']}`",
        "",
        "## Requests Checks",
        "",
        f"- default `trust_env=True`: `{default_query}`",
        f"- `trust_env=False`: `{no_env_query}`",
        f"- known CIF check: `{cif_check}`",
        "",
        "## Client Reuse",
        "",
        "- The historical `scripts/test_cod_search.py` uses a "
        "`requests.Session` with urllib3 retry configuration and the default "
        "environment-proxy behavior.",
        "- `src/crystaldb/sources/cod/__init__.py` uses the same COD endpoint "
        "with manual retry/backoff and default environment-proxy behavior.",
        "- v3 uses the existing `sources.cod` client path with a reusable "
        "session and the verified direct `trust_env=False` setting; it does "
        "not disable TLS verification, set `verify=False`, or invent a proxy "
        "address.",
        "",
        "## Gate",
        "",
        (
            "The COD online gate is satisfied by an HTTP 200 mineral query, "
            "a non-HTML COD ID response, a real CIF response, and successful "
            "Gemmi parsing."
            if cod_online
            else
            "The COD online gate is not satisfied. Do not run the online "
            "pilot or full run; do not interpret the result as no structure."
        ),
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return diagnostics


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, ensure_ascii=False))
