"""Main browser window and navigation workflow for MiiiBrowser."""

import re
import threading
import ssl
import urllib.error
import urllib.parse
import urllib.request
import traceback

import tkinter as tk

try:
    from .colors import ACCENT, BG_TOOLBAR, FG_DIM, FG_TEXT, BG_TITLEBAR, BG_URLBAR, BG_TAB_ACTIVE
    from .tab_bar import TabBar, Toolbar
    from .dom_html_parser import extract_title, render_html
except ImportError:
    from colors import ACCENT, BG_TOOLBAR, FG_DIM, FG_TEXT, BG_TITLEBAR, BG_URLBAR, BG_TAB_ACTIVE
    from tab_bar import TabBar, Toolbar
    from dom_html_parser import extract_title, render_html


class BrowserWindow(tk.Tk):
    """Top-level Tk window that hosts tabs, navigation, and content."""

    _BLOCKED_ASSET_EXTENSIONS = {
        ".js", ".mjs", ".cjs",
        ".ts", ".tsx", ".jsx",
        ".map", ".json",
    }

    _DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Upgrade-Insecure-Requests": "1",
    }

    def __init__(self) -> None:
        super().__init__()
        self.title("MiiiBrowser")
        self.geometry("1100x720")
        self.configure(bg=BG_TOOLBAR)
        self.minsize(600, 400)

        # tab bar
        self.tab_bar = TabBar(self)
        self.tab_bar.pack(fill="x")

        # toolbar
        self.toolbar = Toolbar(self)
        self.toolbar.pack(fill="x", padx=4, pady=(0, 2))
        self.toolbar.on_navigate = self._navigate

        # content area
        self.content = tk.Frame(self, bg=BG_TITLEBAR)
        self.content.pack(fill="both", expand=True)

        # scrollable raw-output text widget
        self.output = tk.Text(
            self.content, bg=BG_TITLEBAR, fg=FG_TEXT,
            font=("Consolas", 10), wrap="word",
            relief="flat", state="disabled",
            insertbackground=FG_TEXT,
        )
        scrollbar = tk.Scrollbar(self.content, command=self.output.yview, bg=BG_TOOLBAR)
        self.output.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.output.pack(fill="both", expand=True)

        # text style tags
        self.output.tag_configure("h1", font=("Segoe UI", 22, "bold"), foreground=FG_TEXT)
        self.output.tag_configure("h2", font=("Segoe UI", 13, "bold"), foreground=FG_TEXT)
        self.output.tag_configure("h3", font=("Segoe UI", 11, "bold"), foreground=FG_TEXT)
        self.output.tag_configure("section", font=("Segoe UI", 11, "bold"), foreground=ACCENT)
        self.output.tag_configure("body", font=("Segoe UI", 10), foreground=FG_TEXT)
        self.output.tag_configure("dim", font=("Segoe UI", 9), foreground=FG_DIM)
        self.output.tag_configure("link", font=("Segoe UI", 9), foreground=ACCENT)
        self.output.tag_configure("divider", foreground="#3c4043")
        self.output.tag_configure("code", font=("Consolas", 10), foreground="#b392f0")
        self.output.tag_configure("pre", font=("Consolas", 10), foreground=FG_TEXT, lmargin1=12, lmargin2=12)
        self.output.tag_configure("blockquote", font=("Segoe UI", 10, "italic"), foreground=FG_DIM, lmargin1=18, lmargin2=28)
        self.output.tag_configure("list", font=("Segoe UI", 10), lmargin1=18, lmargin2=28)
        self.output.tag_configure("table", font=("Consolas", 10), foreground=FG_TEXT)
        self.output.tag_configure("caption", font=("Segoe UI", 9, "italic"), foreground=FG_DIM)
        self.output.tag_configure("img", font=("Segoe UI", 9, "italic"), foreground=FG_DIM)
        self.output.tag_configure("form", font=("Segoe UI", 9), foreground=ACCENT)
        self.output.tag_configure("input", font=("Segoe UI", 9), foreground=FG_DIM)
        self.output.tag_configure("button", font=("Segoe UI", 9, "bold"), foreground=ACCENT)
        self.output.tag_configure("label", font=("Segoe UI", 9, "bold"), foreground=FG_TEXT)
        self._link_counter = 0

        # centered logo on blank page
        self.logo = tk.Label(
            self.output, text="MiiiBrowser", font=("Segoe UI", 28, "bold"),
            bg="#202124", fg=FG_DIM,
        )
        self.output.window_create("end", window=self.logo)

    # ── detect URL vs search query ────────────────────────────────
    _URL_RE = re.compile(r"^(https?://|www\.)\S+|^[\w.-]+\.[a-zA-Z]{2,}(/\S*)?$", re.IGNORECASE)

    def _navigate(self, text: str) -> None:
        """Dispatch the current toolbar input as either a URL or a search."""
        if text == self.toolbar.placeholder or not text.strip():
            return
        query = text.strip()
        # update URL bar
        self.toolbar.entry.configure(state="normal")
        self.toolbar.entry.delete(0, "end")
        self.toolbar.entry.insert(0, query)
        self.toolbar.entry.config(fg=FG_TEXT)
        self._set_plain("Loading…")
        if self._URL_RE.match(query):
            url = query if query.startswith("http") else "https://" + query
            threading.Thread(target=self._fetch_url, args=(url,), daemon=True).start()
        else:
            threading.Thread(target=self._fetch_ddg, args=(query,), daemon=True).start()

    def _fetch_url(self, url: str) -> None:
        """Fetch a web page and render its extracted title and body."""
        try:
            if self._is_blocked_asset_url(url):
                self.after(0, self._set_plain, f"Blocked non-HTML asset: {url}")
                self.after(0, self._set_tab_title, "document")
                return

            raw, final_url = self._request_bytes(url)

            tab_title = extract_title(raw)
            body = render_html(raw, final_url)

        except Exception as exc:
            print(f"Error while fetching {url}:")
            traceback.print_exc()
            body = f"Error: {exc}"
            tab_title = "document"

        self.after(0, self._set_plain, body)
        self.after(0, self._set_tab_title, tab_title)

    def _is_blocked_asset_url(self, url: str) -> bool:
        """Return True for URLs that point to non-HTML asset files."""
        parsed = urllib.parse.urlsplit(url)
        path = parsed.path.lower()
        return any(path.endswith(ext) for ext in self._BLOCKED_ASSET_EXTENSIONS)

    def _fetch_ddg(self, query: str) -> None:
        """Fetch DuckDuckGo HTML search results and render them directly."""
        try:
            params = urllib.parse.urlencode({"q": query, "b": ""}).encode("utf-8")
            url = "https://html.duckduckgo.com/html/"
            raw, final_url = self._request_bytes(
                url,
                data=params,
                extra_headers={
                    "Accept-Encoding": "identity",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Origin": "https://html.duckduckgo.com",
                    "Referer": "https://html.duckduckgo.com/",
                },
                method="POST",
            )

            tab_title = extract_title(raw)
            body = render_html(raw, final_url)
        except Exception as exc:
            print(f"Error while searching DuckDuckGo for {query!r}:")
            traceback.print_exc()
            self.after(0, self._set_plain, f"Error: {exc}")
            return

        self.after(0, self._set_plain, body)
        self.after(0, self._set_tab_title, tab_title)

    def _request_bytes(
        self,
        url: str,
        data: bytes | None = None,
        extra_headers: dict[str, str] | None = None,
        method: str | None = None,
    ) -> tuple[bytes, str]:
        """Fetch bytes with browser-like headers and a no-verify SSL fallback."""
        headers = dict(self._DEFAULT_HEADERS)
        if extra_headers:
            headers.update(extra_headers)

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.read(), resp.geturl()
        except urllib.error.URLError as exc:
            cert_error = getattr(exc, "reason", None)
            if isinstance(cert_error, ssl.SSLCertVerificationError):
                context = ssl._create_unverified_context()
                with urllib.request.urlopen(req, timeout=10, context=context) as resp:
                    return resp.read(), resp.geturl()
            raise

    def _set_tab_title(self, title: str) -> None:
        """Update the active tab title label."""
        if self.tab_bar.tabs:
            self.tab_bar.tabs[0].configure(text=f"  {title}  ")

    def _insert_link(self, text: str, url: str) -> None:
        """Insert a clickable link into the output view."""
        t = self.output
        tag = f"_link_{self._link_counter}"
        self._link_counter += 1
        t.tag_configure(tag, font=("Segoe UI", 9), foreground=ACCENT, underline=True)
        t.tag_bind(tag, "<Enter>",  lambda e: t.configure(cursor="hand2"))
        t.tag_bind(tag, "<Leave>",  lambda e: t.configure(cursor=""))
        t.tag_bind(tag, "<Button-1>", lambda e, u=url: self._navigate(u))
        t.insert("end", text, (tag,))

    def _set_plain(self, text: str) -> None:
        """Replace the content area with plain text."""
        t = self.output
        t.configure(state="normal")
        t.delete("1.0", "end")
        link_start = "\x1eLINK:"
        link_end = "\x1eENDLINK\x1f"
        cursor = 0
        active_link_tag = None

        while cursor < len(text):
            if active_link_tag is None:
                next_start = text.find(link_start, cursor)
                if next_start == -1:
                    t.insert("end", text[cursor:], "body")
                    break

                if next_start > cursor:
                    t.insert("end", text[cursor:next_start], "body")

                link_start_pos = next_start + len(link_start)
                link_url_end = text.find("\x1f", link_start_pos)
                if link_url_end == -1:
                    t.insert("end", text[next_start:], "body")
                    break

                url = urllib.parse.unquote(text[link_start_pos:link_url_end])
                active_link_tag = f"_render_link_{self._link_counter}"
                self._link_counter += 1
                t.tag_configure(active_link_tag, font=("Segoe UI", 10), foreground=ACCENT, underline=True)
                t.tag_bind(active_link_tag, "<Enter>", lambda e: t.configure(cursor="hand2"))
                t.tag_bind(active_link_tag, "<Leave>", lambda e: t.configure(cursor=""))
                t.tag_bind(active_link_tag, "<Button-1>", lambda e, u=url: self._navigate(u))
                cursor = link_url_end + 1
                continue

            next_end = text.find(link_end, cursor)
            if next_end == -1:
                if cursor < len(text):
                    t.insert("end", text[cursor:], ("body", active_link_tag))
                break

            if next_end > cursor:
                t.insert("end", text[cursor:next_end], ("body", active_link_tag))

            active_link_tag = None
            cursor = next_end + len(link_end)

        t.configure(state="disabled")

    def _render_ddg(self, d: dict) -> None:
        """Render a DuckDuckGo JSON response into formatted text."""
        t = self.output
        t.configure(state="normal")
        t.delete("1.0", "end")
        self._link_counter = 0

        def w(text, tag="body"):
            t.insert("end", text, tag)

        def divider():
            w("\n" + "─" * 80 + "\n", "divider")

        heading = d.get("Heading", "")
        if heading:
            w(heading + "\n", "h1")

        abstract = d.get("AbstractText") or d.get("Abstract", "")
        if abstract:
            w(abstract + "\n", "body")
            src_url = d.get("AbstractURL", "")
            src_name = d.get("AbstractSource", "")
            if src_url:
                self._insert_link(f"{src_name}  {src_url}\n", src_url)

        answer = d.get("Answer", "")
        if answer:
            if heading or abstract:
                divider()
            w("Answer\n", "section")
            w(answer + "\n", "body")

        definition = d.get("Definition", "")
        if definition:
            divider()
            w("Definition\n", "section")
            w(definition + "\n", "body")
            def_url = d.get("DefinitionURL", "")
            def_src = d.get("DefinitionSource", "")
            if def_url:
                self._insert_link(f"{def_src}  {def_url}\n", def_url)

        topics = d.get("RelatedTopics", [])
        if topics:
            divider()
            w("Related Topics\n", "section")

            def render_topic(item: dict, indent: str = "  "):
                title_raw = item.get("Text", "")
                url = item.get("FirstURL", "")
                if not title_raw:
                    return
                parts = title_raw.split("  ", 1)
                title = parts[0].strip()
                desc  = parts[1].strip() if len(parts) > 1 else ""
                w(f"\n{indent}", "body")
                w(title, "h2")
                if desc:
                    w(f"\n{indent}  {desc}\n", "body")
                else:
                    w("\n", "body")
                if url:
                    self._insert_link(f"{indent}{url}\n", url)

            for item in topics:
                if "Topics" in item:
                    # grouped sub-section
                    w(f"\n  {item.get('Name', 'More')}\n", "dim")
                    for sub in item["Topics"]:
                        render_topic(sub, indent="    ")
                else:
                    render_topic(item)

        # ── direct results ──
        results = d.get("Results", [])
        if results:
            divider()
            w("Results\n", "section")
            for item in results:
                text = item.get("Text", "")
                url  = item.get("FirstURL", "")
                if text:
                    w(f"\n  {text}\n", "body")
                if url:
                    self._insert_link(f"{url}\n", url)

        if not any([heading, abstract, answer, definition, topics, results]):
            w("No results found.", "dim")

        t.configure(state="disabled")
        t.yview_moveto(0)
