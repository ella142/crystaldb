"""Opaque cursor pagination."""

from __future__ import annotations

import base64
import binascii
import json


def encode_cursor(value: str) -> str:
    payload = json.dumps({"after": value}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> str | None:
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        value = payload.get("after")
        if not isinstance(value, str) or not value:
            raise ValueError
        return value
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError, binascii.Error) as exc:
        raise ValueError("invalid cursor") from exc

