"""Main browser window: tabs, navigation, history, shortcuts, and rendering."""

import re
import base64
import threading
import ssl
import urllib.error
import urllib.parse
import urllib.request
import traceback
from io import BytesIO

import tkinter as tk

try:
    from PIL import Image, ImageTk
except ImportError:  # Pillow drives inline image rendering; degrade gracefully
    Image = None
    ImageTk = None

try:
    from .colors import BG_TOOLBAR, BG_TITLEBAR, FG_DIM, FG_TEXT
    from .tab_bar import TabBar, Toolbar
    from .tab import Tab
    from .dom_html_parser import extract_title, render_html
except ImportError:
    from colors import BG_TOOLBAR, BG_TITLEBAR, FG_DIM, FG_TEXT
    from tab_bar import TabBar, Toolbar
    from tab import Tab
    from dom_html_parser import extract_title, render_html


class BrowserWindow(tk.Tk):
    """Top-level Tk window hosting independent tabs, navigation, and content."""

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

    # detect URL vs search query
    _URL_RE = re.compile(r"^(https?://|www\.)\S+|^[\w.-]+\.[a-zA-Z]{2,}(/\S*)?$", re.IGNORECASE)

    _MAX_IMAGE_WIDTH = 600  # downscale wide images to keep the view readable

    def __init__(self) -> None:
        super().__init__()
        self.title("MiiiBrowser")
        self.geometry("1100x720")
        self.configure(bg=BG_TOOLBAR)
        self.minsize(600, 400)

        # tab bar (the + button creates a new tab)
        self.tab_bar = TabBar(self, on_new=self.new_tab)
        self.tab_bar.pack(fill="x")

        # toolbar
        self.toolbar = Toolbar(self)
        self.toolbar.pack(fill="x", padx=4, pady=(0, 2))
        self.toolbar.on_navigate = self._navigate
        self.toolbar.on_back = self.go_back
        self.toolbar.on_forward = self.go_forward
        self.toolbar.on_reload = self.reload

        # content area — every tab's frame is stacked in this single grid cell
        self.content = tk.Frame(self, bg=BG_TITLEBAR)
        self.content.pack(fill="both", expand=True)
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        # tab model
        self.tabs: list[Tab] = []
        self.active_index: int = -1

        self._bind_shortcuts()
        self.new_tab()  # open the first tab

    # ── tab management (Req 3) ──────────────────────────────────────
    @property
    def active_tab(self) -> Tab | None:
        if 0 <= self.active_index < len(self.tabs):
            return self.tabs[self.active_index]
        return None

    def new_tab(self, event=None) -> str:
        """Open a new, fully isolated tab and focus the address bar."""
        tab = Tab(self, title="New Tab")
        self.tabs.append(tab)
        tab.header = self.tab_bar.add_header(
            "New Tab",
            on_select=lambda t=tab: self.select_tab(self.tabs.index(t)),
            on_close=lambda t=tab: self.close_tab(tab=t),
        )
        self.select_tab(len(self.tabs) - 1)
        self.focus_address_bar()
        return "break"

    def close_tab(self, event=None, tab: Tab | None = None) -> str:
        """Close the given tab (default: the active one)."""
        if not self.tabs:
            return "break"
        if tab is None:
            tab = self.active_tab
        if tab is None or tab not in self.tabs:
            return "break"

        index = self.tabs.index(tab)
        was_active = (index == self.active_index)
        tab.destroy()
        self.tab_bar.remove_header(tab.header)
        self.tabs.pop(index)

        if not self.tabs:  # never leave zero tabs open
            self.active_index = -1
            self.new_tab()
            return "break"

        # Keep the same logical tab selected when a *different* tab was closed.
        if was_active:
            self.active_index = min(index, len(self.tabs) - 1)
        elif index < self.active_index:
            self.active_index -= 1
        self.select_tab(self.active_index)
        return "break"

    def select_tab(self, index: int) -> None:
        """Raise a tab's view and sync the chrome to its state."""
        if not (0 <= index < len(self.tabs)):
            return
        self.active_index = index
        tab = self.tabs[index]
        tab.show()
        self.tab_bar.set_active(index)
        self._sync_toolbar(tab)

    def next_tab(self, event=None) -> str:
        if self.tabs:
            self.select_tab((self.active_index + 1) % len(self.tabs))
        return "break"

    def prev_tab(self, event=None) -> str:
        if self.tabs:
            self.select_tab((self.active_index - 1) % len(self.tabs))
        return "break"

    # ── toolbar / address bar ───────────────────────────────────────
    def _sync_toolbar(self, tab: Tab) -> None:
        """Reflect a tab's URL + nav availability in the shared toolbar."""
        if tab.current_url:
            self._set_address_text(tab.current_url)
        else:
            entry = self.toolbar.entry
            entry.configure(state="normal")
            entry.delete(0, "end")
            entry.insert(0, self.toolbar.placeholder)
            entry.config(fg=FG_DIM)
        self.toolbar.set_nav_state(tab.can_back(), tab.can_forward())

    def _set_address_text(self, text: str) -> None:
        entry = self.toolbar.entry
        entry.configure(state="normal")
        entry.delete(0, "end")
        entry.insert(0, text)
        entry.config(fg=FG_TEXT)

    def focus_address_bar(self, event=None) -> str:
        self.toolbar.focus_address_bar()
        return "break"

    # ── keyboard shortcuts (Req 5) ──────────────────────────────────
    def _bind_shortcuts(self) -> None:
        """Register global keyboard shortcuts.

        Each sequence is bound on the root (``bind_all``, so it works when focus
        is on the page) *and* on the URL entry. The entry binding returns
        ``"break"``, which both runs the action and suppresses the Entry's
        default editing binding for that key (e.g. Ctrl+T would otherwise
        transpose characters in the address bar).
        """
        shortcuts = {
            "<Control-t>": self.new_tab,
            "<Control-w>": self.close_tab,
            "<Control-Tab>": self.next_tab,
            "<Control-Shift-Tab>": self.prev_tab,
            "<Control-ISO_Left_Tab>": self.prev_tab,  # X11 Shift+Tab keysym
            "<Control-l>": self.focus_address_bar,
            "<Control-r>": self.reload,
            "<Alt-Left>": self.go_back,
            "<Alt-Right>": self.go_forward,
            "<F11>": self._toggle_fullscreen,
        }
        for seq, handler in shortcuts.items():
            self.bind_all(seq, handler)
            self.toolbar.entry.bind(seq, handler)

    def _toggle_fullscreen(self, event=None) -> str:
        self.attributes("-fullscreen", not self.attributes("-fullscreen"))
        return "break"

    # ── navigation + history (Req 4) ────────────────────────────────
    def _navigate(self, text: str, tab: Tab | None = None) -> None:
        """Dispatch input as a URL or search for ``tab`` (default: active)."""
        tab = tab or self.active_tab
        if tab is None:
            return
        if text == self.toolbar.placeholder or not text.strip():
            return
        query = text.strip()

        # Record history unless this is a back/forward/reload replay.
        if not tab.in_history_nav:
            tab.push(query)

        if tab is self.active_tab:
            self._set_address_text(query)
            self.toolbar.set_nav_state(tab.can_back(), tab.can_forward())

        tab.render_body("Loading…")
        if self._URL_RE.match(query):
            url = query if query.startswith("http") else "https://" + query
            threading.Thread(target=self._fetch_url, args=(url, tab), daemon=True).start()
        else:
            threading.Thread(target=self._fetch_ddg, args=(query, tab), daemon=True).start()

    def go_back(self, event=None) -> str:
        tab = self.active_tab
        if tab is not None:
            target = tab.back()
            if target is not None:
                self._replay(tab, target)
        return "break"

    def go_forward(self, event=None) -> str:
        tab = self.active_tab
        if tab is not None:
            target = tab.forward()
            if target is not None:
                self._replay(tab, target)
        return "break"

    def reload(self, event=None) -> str:
        tab = self.active_tab
        if tab is not None:
            target = tab.reload_target()
            if target is not None:
                self._replay(tab, target)
        return "break"

    def _replay(self, tab: Tab, target: str) -> None:
        """Re-navigate to a history/reload target without pushing a new entry."""
        tab.in_history_nav = True
        try:
            self._navigate(target, tab)
        finally:
            tab.in_history_nav = False

    # ── fetching ────────────────────────────────────────────────────
    def _fetch_url(self, url: str, tab: Tab) -> None:
        """Fetch a web page (worker thread) and apply it to its tab."""
        try:
            if self._is_blocked_asset_url(url):
                self.after(0, self._apply_load, tab, f"Blocked non-HTML asset: {url}", "document", url)
                return
            raw, final_url = self._request_bytes(url)
            tab_title = extract_title(raw)
            body = render_html(raw, final_url)
        except Exception as exc:
            print(f"Error while fetching {url}:")
            traceback.print_exc()
            self.after(0, self._apply_load, tab, f"Error: {exc}", "document", url)
            return
        self.after(0, self._apply_load, tab, body, tab_title, final_url)

    def _fetch_ddg(self, query: str, tab: Tab) -> None:
        """Fetch DuckDuckGo HTML results (worker thread) and apply them to its tab."""
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
            self.after(0, self._apply_load, tab, f"Error: {exc}", "document", query)
            return
        # Keep the typed query (not the DDG endpoint) in the address bar.
        self.after(0, self._apply_load, tab, body, tab_title, query)

    def _is_blocked_asset_url(self, url: str) -> bool:
        """Return True for URLs that point to non-HTML asset files."""
        parsed = urllib.parse.urlsplit(url)
        path = parsed.path.lower()
        return any(path.endswith(ext) for ext in self._BLOCKED_ASSET_EXTENSIONS)

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

    def _apply_load(self, tab: Tab, body: str, title: str, display_url: str | None) -> None:
        """Apply a finished load to its originating tab only (main thread)."""
        if tab not in self.tabs:
            return  # tab was closed mid-load — discard
        if display_url:
            tab.current_url = display_url
        tab.title = title or "document"
        tab.render_body(body)
        if tab.header is not None:
            self.tab_bar.set_title(tab.header, tab.title)
        # Touch the shared chrome only if this tab is the visible one.
        if tab is self.active_tab:
            if display_url:
                self._set_address_text(display_url)
            self.toolbar.set_nav_state(tab.can_back(), tab.can_forward())

    # ── inline image rendering (Req 2) ──────────────────────────────
    def load_image_async(self, tab: Tab, slot: str, src: str, alt: str) -> None:
        """Start an off-thread fetch+decode of an <img>; no-op without Pillow."""
        if Image is None:  # Pillow unavailable — keep the [image: alt] placeholder
            return
        threading.Thread(target=self._fetch_image, args=(tab, slot, src), daemon=True).start()

    def _fetch_image(self, tab: Tab, slot: str, src: str) -> None:
        """Download and decode an image; on any failure keep the placeholder."""
        try:
            if src.startswith("data:"):
                raw = self._decode_data_uri(src)
            else:
                raw, _ = self._request_bytes(src)
            image = Image.open(BytesIO(raw))
            image.load()
            if getattr(image, "is_animated", False):
                image.seek(0)  # first frame of animated GIFs
            image = image.convert("RGBA")
            # Downscale wide images, preserving aspect ratio.
            image.thumbnail((self._MAX_IMAGE_WIDTH, 4000))
        except Exception as exc:
            print(f"Image load failed for {src}: {exc}")
            return  # leave the [image: alt] placeholder in place
        self.after(0, self._embed_image, tab, slot, image)

    def _embed_image(self, tab: Tab, slot: str, image) -> None:
        """Build the PhotoImage and hand it to the tab (main thread)."""
        if tab not in self.tabs or ImageTk is None:
            return
        try:
            photo = ImageTk.PhotoImage(image)
        except Exception as exc:
            print(f"Image embed failed: {exc}")
            return
        tab.insert_image_widget(slot, photo)

    @staticmethod
    def _decode_data_uri(uri: str) -> bytes:
        """Decode a ``data:`` image URI into raw bytes."""
        header, _, data = uri.partition(",")
        if ";base64" in header.lower():
            return base64.b64decode(data)
        return urllib.parse.unquote_to_bytes(data)
