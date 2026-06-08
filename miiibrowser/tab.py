"""Per-tab view, state, and HTML-to-Text rendering for MiiiBrowser.

Each :class:`Tab` owns a fully isolated content view (its own ``tk.Text``
widget), its own navigation history, and its own current URL/title. Tabs are
completely independent: a page (or image) load that finishes in a background
tab updates only that tab and never the one the user is currently viewing.
"""

from __future__ import annotations

import urllib.parse
from typing import TYPE_CHECKING

import tkinter as tk

try:
    from .colors import ACCENT, BG_TITLEBAR, FG_DIM, FG_TEXT
    from .dom_html_parser import _IMG_END, _IMG_SEP, _IMG_START, _LINK_END, _LINK_START
except ImportError:  # running as loose scripts (e.g. `python BrowserWindow.py`)
    from colors import ACCENT, BG_TITLEBAR, FG_DIM, FG_TEXT
    from dom_html_parser import _IMG_END, _IMG_SEP, _IMG_START, _LINK_END, _LINK_START

if TYPE_CHECKING:  # avoid a runtime circular import
    from .BrowserWindow import BrowserWindow


class Tab:
    """One browser tab: an isolated view widget + navigation history + state."""

    def __init__(self, window: "BrowserWindow", title: str = "New Tab") -> None:
        self.window = window
        self.title = title

        # ── isolated navigation state ───────────────────────────────
        self.history: list[str] = []      # navigation targets (URLs / queries)
        self.history_index: int = -1      # cursor into self.history
        self.current_url: str | None = None
        self.in_history_nav: bool = False  # guard: suppress history push on back/fwd

        # ── render bookkeeping ──────────────────────────────────────
        self._link_counter = 0
        self._img_slot = 0
        self._image_refs: list[tk.Image] = []  # keep PhotoImages alive (Tk GC)
        self.header = None                       # the TabBar header (set by window)

        # ── isolated view widget ────────────────────────────────────
        # Every tab frame shares the same grid cell in window.content; switching
        # tabs is just a tkraise() of the active frame.
        self.frame = tk.Frame(window.content, bg=BG_TITLEBAR)
        self.frame.grid(row=0, column=0, sticky="nsew")

        self.view = tk.Text(
            self.frame, bg=BG_TITLEBAR, fg=FG_TEXT,
            font=("Consolas", 10), wrap="word",
            relief="flat", state="disabled",
            insertbackground=FG_TEXT,
        )
        scrollbar = tk.Scrollbar(self.frame, command=self.view.yview, bg=BG_TITLEBAR)
        self.view.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.view.pack(fill="both", expand=True)

        self._configure_tags()
        self.show_logo()

    # ── view setup ──────────────────────────────────────────────────
    def _configure_tags(self) -> None:
        """Configure text style tags for this tab's view."""
        v = self.view
        v.tag_configure("body", font=("Segoe UI", 10), foreground=FG_TEXT)
        v.tag_configure("dim", font=("Segoe UI", 9), foreground=FG_DIM)
        v.tag_configure("link", font=("Segoe UI", 10), foreground=ACCENT, underline=True)
        v.tag_configure("img", font=("Segoe UI", 9, "italic"), foreground=FG_DIM)

    def show_logo(self) -> None:
        """Show the centered brand label on the blank/new-tab page."""
        v = self.view
        v.configure(state="normal")
        v.delete("1.0", "end")
        logo = tk.Label(
            v, text="MiiiBrowser", font=("Segoe UI", 28, "bold"),
            bg=BG_TITLEBAR, fg=FG_DIM,
        )
        v.window_create("end", window=logo)
        v.configure(state="disabled")

    # ── tab switching / teardown ────────────────────────────────────
    def show(self) -> None:
        """Raise this tab's view to the front of the content stack."""
        self.frame.tkraise()

    def destroy(self) -> None:
        """Tear down the tab's widgets and release image references."""
        self._image_refs.clear()
        self.frame.destroy()

    # ── navigation history (Req 4) ──────────────────────────────────
    def push(self, target: str) -> None:
        """Record a fresh navigation, truncating any forward history."""
        del self.history[self.history_index + 1:]
        self.history.append(target)
        self.history_index = len(self.history) - 1

    def can_back(self) -> bool:
        return self.history_index > 0

    def can_forward(self) -> bool:
        return self.history_index < len(self.history) - 1

    def back(self) -> str | None:
        if not self.can_back():
            return None
        self.history_index -= 1
        return self.history[self.history_index]

    def forward(self) -> str | None:
        if not self.can_forward():
            return None
        self.history_index += 1
        return self.history[self.history_index]

    def reload_target(self) -> str | None:
        if 0 <= self.history_index < len(self.history):
            return self.history[self.history_index]
        return self.current_url

    # ── rendering (Req 2 + Req 6) ───────────────────────────────────
    def render_body(self, text: str) -> None:
        """Render parser output (plain text + link/image sentinels) into view.

        Wrapped end-to-end so malformed sentinel data or a Tk error degrades to
        a raw-text dump instead of crashing the UI.
        """
        v = self.view
        try:
            v.configure(state="normal")
            v.delete("1.0", "end")
            self._image_refs.clear()
            self._render_tokens(text)
        except Exception as exc:  # graceful degradation
            print(f"render_body failed: {exc}")
            try:
                v.delete("1.0", "end")
                v.insert("end", text, "body")
            except Exception:
                pass
        finally:
            try:
                v.configure(state="disabled")
                v.yview_moveto(0)
            except Exception:
                pass

    def _render_tokens(self, text: str) -> None:
        """Walk the sentinel-bearing text, inserting plain text, links, images."""
        i, n = 0, len(text)
        active_link_tag: str | None = None

        while i < n:
            # Find the nearest sentinel of any recognised kind from position i.
            candidates: list[tuple[int, str]] = []
            p = text.find(_LINK_START, i)
            if p != -1:
                candidates.append((p, "link"))
            if active_link_tag is not None:
                p = text.find(_LINK_END, i)
                if p != -1:
                    candidates.append((p, "endlink"))
            p = text.find(_IMG_START, i)
            if p != -1:
                candidates.append((p, "img"))

            if not candidates:
                self._insert_text(text[i:], active_link_tag)
                break

            pos, kind = min(candidates, key=lambda c: c[0])
            if pos > i:
                self._insert_text(text[i:pos], active_link_tag)

            if kind == "endlink":
                active_link_tag = None
                i = pos + len(_LINK_END)
            elif kind == "link":
                url_start = pos + len(_LINK_START)
                url_end = text.find("\x1f", url_start)
                if url_end == -1:  # malformed sentinel: emit the rest as text
                    self._insert_text(text[pos:], active_link_tag)
                    break
                url = urllib.parse.unquote(text[url_start:url_end])
                active_link_tag = self._make_link_tag(url)
                i = url_end + 1
            else:  # image
                end = text.find(_IMG_END, pos)
                if end == -1:
                    self._insert_text(text[pos:], active_link_tag)
                    break
                payload = text[pos + len(_IMG_START):end]
                src_q, _, alt = payload.partition(_IMG_SEP)
                self._insert_image(urllib.parse.unquote(src_q), alt, active_link_tag)
                i = end + len(_IMG_END)

    def _insert_text(self, chunk: str, link_tag: str | None) -> None:
        if not chunk:
            return
        tags = ("body", link_tag) if link_tag else ("body",)
        self.view.insert("end", chunk, tags)

    def _make_link_tag(self, url: str) -> str:
        """Create a unique clickable tag that navigates *this* tab on click."""
        v = self.view
        tag = f"_link_{self._link_counter}"
        self._link_counter += 1
        v.tag_configure(tag, font=("Segoe UI", 10), foreground=ACCENT, underline=True)
        v.tag_bind(tag, "<Enter>", lambda e: v.configure(cursor="hand2"))
        v.tag_bind(tag, "<Leave>", lambda e: v.configure(cursor=""))
        # Link clicks navigate the tab the link lives in (Req 3 isolation, Req 4).
        v.tag_bind(tag, "<Button-1>", lambda e, u=url: self.window._navigate(u, self))
        return tag

    def _insert_image(self, src: str, alt: str, link_tag: str | None) -> None:
        """Insert an [image: …] placeholder and kick off async image loading."""
        v = self.view
        slot = f"_img_{self._img_slot}"
        self._img_slot += 1
        placeholder = f"[image: {alt or src or 'image'}]"
        tags = ["img", slot]
        if link_tag:
            tags.append(link_tag)
        v.insert("end", placeholder, tuple(tags))
        if src:
            self.window.load_image_async(self, slot, src, alt)

    def insert_image_widget(self, slot: str, photo) -> None:
        """Replace the placeholder tagged ``slot`` with the real image (main thread)."""
        v = self.view
        try:
            ranges = v.tag_ranges(slot)
            if not ranges:  # placeholder gone (tab re-rendered) — drop silently
                return
            start, end = ranges[0], ranges[1]
            v.configure(state="normal")
            v.delete(start, end)
            v.image_create(start, image=photo)
            self._image_refs.append(photo)  # keep a live reference
        except Exception as exc:
            print(f"insert_image_widget failed: {exc}")
        finally:
            try:
                v.configure(state="disabled")
            except Exception:
                pass
