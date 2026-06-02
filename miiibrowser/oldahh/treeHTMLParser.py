"""Lightweight HTML parser that builds a tree of visible and hidden nodes."""

from html.parser import HTMLParser


class TreeHTMLParser(HTMLParser):
    """Parse HTML into a simple nested dictionary structure."""

    _VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr",
    }

    _INVISIBLE_TAGS = {
        "script", "style", "link", "meta", "noscript",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = {"type": "root", "children": []}
        self._stack = [self.root]
        self.invisible_tags = []
        self._invisible_stack = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Handle the start of an HTML element."""
        node = {
            "type": "element",
            "tag": tag,
            "attrs": {k: v for k, v in attrs if k},
            "children": [],
        }

        # If we are already inside an invisible tag, keep collecting into that branch.
        if self._invisible_stack:
            self._invisible_stack[-1]["children"].append(node)
            if tag not in self._VOID_TAGS:
                self._invisible_stack.append(node)
            return

        # Start a new invisible branch for configured tags.
        if tag in self._INVISIBLE_TAGS:
            self.invisible_tags.append(node)
            if tag in self._VOID_TAGS:
                # Void tags like <meta>, <link> are complete as-is.
                return
            else:
                # Non-void tags like <script>, <style> can contain nested data.
                self._invisible_stack.append(node)
            return

        # Add to visible tree.
        self._stack[-1]["children"].append(node)
        if tag not in self._VOID_TAGS:
            self._stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        """Handle the end of an HTML element."""
        # Close inside invisible branch first.
        if self._invisible_stack:
            for idx in range(len(self._invisible_stack) - 1, -1, -1):
                node = self._invisible_stack[idx]
                if node.get("tag") == tag:
                    del self._invisible_stack[idx:]
                    break
            return

        # Close visible branch.
        for idx in range(len(self._stack) - 1, 0, -1):
            node = self._stack[idx]
            if node.get("type") == "element" and node.get("tag") == tag:
                del self._stack[idx:]
                break

    def handle_data(self, data: str) -> None:
        """Store text nodes after collapsing internal whitespace."""
        text = " ".join(data.split())
        if not text:
            return

        # Store content in invisible branch when currently inside one.
        if self._invisible_stack:
            self._invisible_stack[-1]["children"].append({"type": "text", "value": text})
            return

        # Store visible text
        self._stack[-1]["children"].append({"type": "text", "value": text})
