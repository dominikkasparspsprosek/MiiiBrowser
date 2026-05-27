"""HTML normalization and text rendering helpers for MiiiBrowser."""

from __future__ import annotations

import re
from typing import Any, Callable
from xml.dom.minidom import Node, parseString
from xml.parsers.expat import ExpatError
from html.entities import name2codepoint

try:
    from .charset_parser import decode_html
except ImportError:
    from charset_parser import decode_html

_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}

_INVISIBLE_TAGS = {"script", "style", "link", "meta", "noscript"}
_BLOCK_TAGS = {
    "article", "aside", "blockquote", "body", "div", "fieldset", "figure",
    "footer", "form", "header", "main", "nav", "p", "section", "table",
    "tbody", "thead", "tfoot", "tr", "ul", "ol", "li",
}
_INLINE_BREAK_TAGS = {"a", "abbr", "b", "big", "cite", "code", "em", "i", "kbd", "q", "s", "small", "span", "strong", "sub", "sup", "u", "var"}


def _normalize_html(html_string: str) -> str:
    """Preprocess HTML so the XML parser can consume it safely."""
    text = html_string.lstrip("\ufeff")
    text = re.sub(r"<!DOCTYPE[^>]*>", "", text, flags=re.IGNORECASE)

    for tag in _INVISIBLE_TAGS:
        text = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", "", text, flags=re.IGNORECASE | re.DOTALL)

    # convert named HTML entities to numeric references (e.g. &nbsp; -> &#160;)
    def _named_entity_repl(m: re.Match[str]) -> str:
        name = m.group(1)
        cp = name2codepoint.get(name)
        if cp is not None:
            return f"&#{cp};"
        # unknown entity -> escape ampersand so parser won't treat as entity
        return f"&amp;{name};"

    text = re.sub(r"&([A-Za-z][A-Za-z0-9]+);", _named_entity_repl, text)

    unsafe_amp = re.compile(r"&(?!#\d+;|#x[0-9A-Fa-f]+;)")
    text = unsafe_amp.sub("&amp;", text)

    # self-close void tags to help the XML parser
    for tag in _VOID_TAGS:
            def _self_close_void_tag(match: re.Match[str]) -> str:
                attrs = (match.group(2) or "").rstrip()
                attrs = re.sub(r"\s*/+$", "", attrs)
                return f"<{match.group(1)}{attrs}/>"

            text = re.sub(rf"<({tag})(\s[^<>]*?)?>", _self_close_void_tag, text, flags=re.IGNORECASE)
    # convert common boolean attributes inside tags to explicit attributes
    bool_attrs = [
        "async", "defer", "autoplay", "controls", "muted", "loop",
        "selected", "checked", "disabled", "multiple", "required",
        "hidden", "readonly", "scoped", "novalidate", "open",
        "itemscope", "allowfullscreen", "allowpaymentrequest",
    ]

    def _fix_tag(match: re.Match[str]) -> str:
        tag = match.group(0)
        for b in bool_attrs:
            # replace occurrences like ' async' or ' async>' or ' async/' with async="async"
            tag = re.sub(
                rf"(\s)({b})(?=(\s|>|/))",
                lambda m, _b=b: m.group(1) + m.group(2) + '="' + m.group(2) + '"',
                tag,
                flags=re.IGNORECASE,
            )
        return tag

    text = re.sub(r"<[^>]+>", _fix_tag, text)

    return f"<document>{text}</document>"


def _ensure_utf8(html_input: bytes | str) -> str:
    """Decode HTML bytes using the local charset parser."""
    return decode_html(html_input)


def _log_parse_error_context(html_string: str, exc: Exception) -> None:
    """Print a small excerpt around an XML parse error to the console."""
    line_no = getattr(exc, "lineno", None)
    column_no = getattr(exc, "offset", None)
    if not isinstance(line_no, int) or line_no < 1:
        print(f"Parse error context unavailable: {exc}")
        return

    lines = html_string.splitlines() or [html_string]
    if line_no > len(lines):
        line_no = len(lines)

    line_text = lines[line_no - 1]
    print(f"Parse error at line {line_no}, column {column_no or '?'}")

    if isinstance(column_no, int) and column_no > 0:
        radius = 120
        center = column_no - 1
        start = max(0, center - radius)
        end = min(len(line_text), center + radius)
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(line_text) else ""
        excerpt = line_text[start:end]
        print(f"{prefix}{excerpt}{suffix}")
        print(" " * (len(prefix) + max(0, center - start)) + "^")
    else:
        print(line_text)


def extract_title(html_string: bytes | str) -> str:
    """Return a cleaned document title or a fallback label."""
    try:
        html_string = _ensure_utf8(html_string)
        document = parseString(_normalize_html(html_string))
        titles = document.getElementsByTagName("title")
        if not titles:
            return "document"
        title_node = titles[0]
        pieces: list[str] = []
        for child in title_node.childNodes:
            if child.nodeType in {Node.TEXT_NODE, Node.CDATA_SECTION_NODE}:
                pieces.append(getattr(child, "data", ""))
        title = " ".join(" ".join(pieces).split())
        return title or "document"
    except Exception:
        return "document"


def render_before(node: Any, writer: Callable[[str], None]) -> None:
    """Write any prefix text that should appear before a node's children."""
    if node.nodeType == node.TEXT_NODE:
        writer(node.data)
        return

    if node.nodeType != node.ELEMENT_NODE:
        return

    tag = node.tagName.lower()

    if tag == "head":
        title_nodes = node.getElementsByTagName("title")
        if title_nodes and title_nodes[0].firstChild is not None:
            writer(title_nodes[0].firstChild.data)
            writer("\n-----------------------\n")
        return

    if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        writer("\n-----------------------\n")
        return

    if tag == "table":
        writer("-----------------------\n")
        return

    if tag in {"ul", "ol"}:
        writer("\n")
        return

    if tag == "li":
        parent = getattr(node, "parentNode", None)
        if parent is not None and getattr(parent, "tagName", "").lower() == "ol":
            index = 1
            for sibling in getattr(parent, "childNodes", []):
                if sibling is node:
                    break
                if getattr(sibling, "tagName", "").lower() == "li":
                    index += 1
            writer(f"{index}. ")
        else:
            writer("- ")
        return

    if tag == "blockquote":
        writer("> ")
        return

    if tag == "hr":
        writer("\n-----------------------\n")
        return

    if tag == "br":
        writer("\n")
        return

    if tag == "img":
        alt_text = node.getAttribute("alt") if node.hasAttribute("alt") else ""
        src = node.getAttribute("src") if node.hasAttribute("src") else ""
        label = alt_text or src or "image"
        writer(f"[image: {label}]")
        return

    if tag == "a":
        href = node.getAttribute("href") if node.hasAttribute("href") else ""
        if href:
            writer("")
        return

    if tag == "code" and node.parentNode is not None and getattr(node.parentNode, "tagName", "").lower() != "pre":
        writer("`")
        return

    if tag in {"input", "textarea", "select", "button", "label"}:
        if tag == "label":
            writer("[label] ")
        elif tag == "button":
            label = node.getAttribute("value") if node.hasAttribute("value") else "button"
            writer(f"[button: {label}] ")
        else:
            input_type = node.getAttribute("type") if node.hasAttribute("type") else tag
            name = node.getAttribute("name") if node.hasAttribute("name") else ""
            placeholder = node.getAttribute("placeholder") if node.hasAttribute("placeholder") else ""
            details = ", ".join(part for part in [name and f"name={name}", placeholder and f"placeholder={placeholder}"] if part)
            writer(f"[{input_type}{': ' + details if details else ''}] ")
        return


def render_allow_children(node: Any) -> bool:
    """Return whether the renderer should recurse into this node."""
    if node.nodeType != node.ELEMENT_NODE:
        return True

    tag = node.tagName.lower()
    if tag in _INVISIBLE_TAGS:
        return False
    if tag == "head":
        return False
    if tag in _VOID_TAGS:
        return False
    return True


def containstext(node: Any) -> bool:
        """Check whether the node has any non-empty text children."""
        for child in getattr(node, "childNodes", []):
                if child.nodeType == child.TEXT_NODE and child.data.strip():
                        return True
        return False



def render_after(node: Any, writer: Callable[[str], None]) -> None:
    """Write any suffix text that should appear after a node's children."""
    if node.nodeType != node.ELEMENT_NODE:
        return

    tag = node.tagName.lower()

    if tag in {"p", "div", "section", "article", "aside", "main", "header", "footer", "nav"}:
      if (containstext(node)):
        writer("\n")
        return
      return

    if tag in {"tr", "li"}:
      if (containstext(node)):
        writer("\n")
        return
      return

    if tag == "table":
      if (containstext(node)):
        writer("-----------------------\n")
        return
      return

    if tag == "blockquote":
      if (containstext(node)):
        writer("\n")
        return
      return

    if tag in {"pre", "form", "fieldset"}:
      if (containstext(node)):
        writer("\n")
        return
      return

    if tag == "code" and node.parentNode is not None and getattr(node.parentNode, "tagName", "").lower() != "pre":
        writer("`")


def render(node: Any, writer: Callable[[str], None]) -> None:
    """Render a DOM node tree into plain text."""
    render_before(node, writer)
    for child in getattr(node, "childNodes", []):
        if render_allow_children(child):
            render(child, writer)
    render_after(node, writer)


def render_html(html_string: bytes | str) -> str:
    """Render HTML input into readable plain text."""
    html_string = _ensure_utf8(html_string)
    normalized_html = _normalize_html(html_string)
    try:
        document = parseString(normalized_html)
    except ExpatError as exc:
        print(f"HTML parse failed: {exc}")
        _log_parse_error_context(normalized_html, exc)
        raise
    content = ""

    def writer(text: str):
        nonlocal content
        content += text

    render(document, writer)
    return content