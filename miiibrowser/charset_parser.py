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
    """Guess the most likely HTML encoding from BOM and in-band hints.

    A byte-order mark always wins. Otherwise the ``<meta charset>`` /
    ``<meta http-equiv>`` / XML declaration are searched only within the
    document's ``<head>`` region (per the HTML spec the encoding declaration
    must appear early), so a stray ``charset=`` later in the body or inside a
    comment can't mislead detection. Falls back to ``"utf-8"`` when no hint is
    found; decoding errors are then handled by :func:`decode_html`.
    """
    # BOM is checked on the raw document start and takes precedence.
    for bom, encoding in (
        (codecs.BOM_UTF8, "utf-8-sig"),
        (codecs.BOM_UTF16_LE, "utf-16-le"),
        (codecs.BOM_UTF16_BE, "utf-16-be"),
        (codecs.BOM_UTF32_LE, "utf-32-le"),
        (codecs.BOM_UTF32_BE, "utf-32-be"),
    ):
        if html_bytes.startswith(bom):
            return encoding

    # Restrict meta/XML sniffing to <head>: scan a generous 8 KB window but stop
    # at </head> or the start of <body>. The XML declaration (if any) sits before
    # <head> and so is still inside this slice.
    window = html_bytes[:8192]
    lowered = window.lower()
    head_end = len(window)
    for marker in (b"</head>", b"<body"):
        idx = lowered.find(marker)
        if idx != -1:
            head_end = min(head_end, idx)
    sample = window[:head_end] if head_end else window[:4096]

    for pattern in (_XML_ENCODING_RE, _META_CHARSET_RE, _META_HTTP_EQUIV_RE):
        match = pattern.search(sample)
        if match:
            encoding = _normalize_encoding(match.group(1))
            if encoding:
                return encoding

    return "utf-8"


def decode_html(html_input: bytes | str) -> str:
    """Decode HTML bytes to a Unicode ``str`` using charset sniffing.

    The returned ``str`` is the UTF-8-clean text representation suitable for
    rendering in Tk (no pointless re-encode to UTF-8 *bytes* is needed). Decoding
    never raises: it falls back through the sniffed encoding, then UTF-8,
    Windows-1252, Latin-1 (ISO-8859-1), and finally a lossy UTF-8 decode with
    ``errors="replace"``.
    """
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