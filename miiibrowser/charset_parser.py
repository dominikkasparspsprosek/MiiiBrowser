"""Local HTML charset detection and decoding helpers."""

from __future__ import annotations

import codecs
import re


_META_CHARSET_RE = re.compile(
    rb"<meta\s+[^>]*charset\s*=\s*['\"]?\s*([a-zA-Z0-9._\-]+)\s*['\"]?",
    re.IGNORECASE,
)
_META_HTTP_EQUIV_RE = re.compile(
    rb"<meta\s+[^>]*http-equiv\s*=\s*['\"]content-type['\"][^>]*content\s*=\s*['\"][^>]*charset\s*=\s*([a-zA-Z0-9._\-]+)",
    re.IGNORECASE,
)
_XML_ENCODING_RE = re.compile(
    rb"<\?xml\s+[^>]*encoding\s*=\s*['\"]([a-zA-Z0-9._\-]+)['\"]",
    re.IGNORECASE,
)


def _normalize_encoding(name: bytes | bytearray | memoryview | str | None) -> str | None:
    """Normalize an encoding label to a canonical codec name."""
    if not name:
        return None

    if not isinstance(name, str):
        try:
            name = bytes(name).decode("ascii", errors="ignore")
        except Exception:
            return None

    name = name.strip().lower().replace("_", "-")
    if not name:
        return None

    try:
        return codecs.lookup(name).name
    except LookupError:
        return None


def sniff_encoding(html_bytes: bytes) -> str:
    """Guess the most likely HTML encoding from BOM and in-band hints."""
    sample = html_bytes[:4096]

    for bom, encoding in (
        (codecs.BOM_UTF8, "utf-8-sig"),
        (codecs.BOM_UTF16_LE, "utf-16-le"),
        (codecs.BOM_UTF16_BE, "utf-16-be"),
        (codecs.BOM_UTF32_LE, "utf-32-le"),
        (codecs.BOM_UTF32_BE, "utf-32-be"),
    ):
        if sample.startswith(bom):
            return encoding

    for pattern in (_XML_ENCODING_RE, _META_CHARSET_RE, _META_HTTP_EQUIV_RE):
        match = pattern.search(sample)
        if match:
            encoding = _normalize_encoding(match.group(1))
            if encoding:
                return encoding

    return "utf-8"


def decode_html(html_input: bytes | str) -> str:
    """Decode HTML bytes to text using the local sniffing heuristics."""
    if isinstance(html_input, str):
        return html_input

    if not isinstance(html_input, bytes):
        try:
            html_input = bytes(html_input)
        except Exception:
            return str(html_input)

    encoding = sniff_encoding(html_input)
    try:
        return html_input.decode(encoding)
    except Exception:
        pass

    for fallback in ("utf-8", "windows-1252", "latin-1"):
        try:
            return html_input.decode(fallback)
        except Exception:
            continue

    return html_input.decode("utf-8", errors="replace")