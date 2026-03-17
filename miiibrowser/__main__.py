import tkinter as tk
from tkinter import ttk
import threading
import urllib.request
import urllib.parse
import json
import re


# ── colour palette ──────────────────────────────
BG_TITLEBAR  = "#202124"
BG_TAB       = "#35363a"
BG_TAB_ACTIVE = "#292a2d"
BG_TOOLBAR   = "#292a2d"
FG_TEXT       = "#e8eaed"
FG_DIM        = "#9aa0a6"
BG_URLBAR     = "#202124"
ACCENT        = "#8ab4f8"


class TabBar(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=BG_TITLEBAR)
        self.tabs: list[tk.Label] = []
        self._build()

    def _build(self):
        # one default tab
        self._add_tab("New Tab")

        # '+' button
        self.new_btn = tk.Label(
            self, text=" + ", font=("Segoe UI", 11),
            bg=BG_TITLEBAR, fg=FG_DIM, cursor="hand2",
            padx=6, pady=4,
        )
        self.new_btn.pack(side="left", padx=(2, 0))

    def _add_tab(self, title: str):
        tab = tk.Label(
            self, text=f"  {title}  ", font=("Segoe UI", 10),
            bg=BG_TAB_ACTIVE, fg=FG_TEXT,
            padx=12, pady=6, relief="flat",
        )
        tab.pack(side="left", padx=(2, 0), pady=(4, 0))
        self.tabs.append(tab)


class Toolbar(tk.Frame):
    """Navigation buttons + URL / search bar."""

    def __init__(self, master):
        super().__init__(master, bg=BG_TOOLBAR)
        self._build()

    def _build(self):
        btn_cfg = dict(
            font=("Segoe UI", 13), bg=BG_TOOLBAR, fg=FG_DIM,
            bd=0, padx=6, pady=2, cursor="hand2",
            activebackground=BG_TOOLBAR, activeforeground=FG_TEXT,
        )
        # back / forward / reload
        for symbol in ("←", "→", "⟳"):
            tk.Button(self, text=symbol, **btn_cfg).pack(side="left", padx=2)

        # URL / search bar
        self.url_var = tk.StringVar()
        entry = tk.Entry(
            self, textvariable=self.url_var,
            font=("Segoe UI", 11), bg=BG_URLBAR, fg=FG_TEXT,
            insertbackground=FG_TEXT, relief="flat",
            highlightthickness=1, highlightcolor=ACCENT,
            highlightbackground="#5f6368",
        )
        entry.pack(side="left", fill="x", expand=True, padx=8, ipady=6)

        # placeholder behaviour
        placeholder = "Search DuckDuckGo or type a URL"
        entry.insert(0, placeholder)
        entry.config(fg=FG_DIM)

        def _on_focus_in(e):
            if entry.get() == placeholder:
                entry.delete(0, "end")
                entry.config(fg=FG_TEXT)

        def _on_focus_out(e):
            if not entry.get():
                entry.insert(0, placeholder)
                entry.config(fg=FG_DIM)

        entry.bind("<FocusIn>", _on_focus_in)
        entry.bind("<FocusOut>", _on_focus_out)
        entry.bind("<Return>", lambda e: self.on_navigate(entry.get()))
        self.entry = entry
        self.placeholder = placeholder

    def on_navigate(self, text):
        pass  # overridden by BrowserWindow


class BrowserWindow(tk.Tk):
    """Top-level window that assembles the Chrome-like UI."""

    def __init__(self):
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
        self.content = tk.Frame(self, bg="#202124")
        self.content.pack(fill="both", expand=True)

        # scrollable raw-output text widget
        self.output = tk.Text(
            self.content, bg="#202124", fg=FG_TEXT,
            font=("Consolas", 10), wrap="word",
            relief="flat", state="disabled",
            insertbackground=FG_TEXT,
        )
        scrollbar = tk.Scrollbar(self.content, command=self.output.yview, bg=BG_TOOLBAR)
        self.output.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.output.pack(fill="both", expand=True)

        # centered logo on blank page
        self.logo = tk.Label(
            self.output, text="MiiiBrowser", font=("Segoe UI", 28, "bold"),
            bg="#202124", fg=FG_DIM,
        )
        self.output.window_create("end", window=self.logo)

    # ── detect URL vs search query ────────────────────────────────
    _URL_RE = re.compile(r"^(https?://|www\.)\S+", re.IGNORECASE)

    def _navigate(self, text: str):
        if text == self.toolbar.placeholder or not text.strip():
            return
        query = text.strip()
        self._set_output("Loading…")
        if self._URL_RE.match(query):
            url = query if query.startswith("http") else "https://" + query
            threading.Thread(target=self._fetch_url, args=(url,), daemon=True).start()
        else:
            threading.Thread(target=self._fetch_ddg, args=(query,), daemon=True).start()

    def _fetch_url(self, url: str):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MiiiBrowser/0.1"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except Exception as exc:
            raw = f"Error: {exc}"
        self.after(0, self._set_output, raw)

    def _fetch_ddg(self, query: str):
        try:
            params = urllib.parse.urlencode({"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"})
            url = f"https://api.duckduckgo.com/?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "MiiiBrowser/0.1"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            # pretty-print JSON
            raw = json.dumps(json.loads(raw), indent=2, ensure_ascii=False)
        except Exception as exc:
            raw = f"Error: {exc}"
        self.after(0, self._set_output, raw)

    def _set_output(self, text: str):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("end", text)
        self.output.configure(state="disabled")


def main():
    app = BrowserWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
