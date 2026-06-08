"""Tab bar and toolbar widgets for the MiiiBrowser window."""

import tkinter as tk

try:
    from .colors import ACCENT, BG_TAB, BG_TAB_ACTIVE, BG_TITLEBAR, BG_TOOLBAR, BG_URLBAR, FG_DIM, FG_TEXT
except ImportError:  # running as loose scripts
    from colors import ACCENT, BG_TAB, BG_TAB_ACTIVE, BG_TITLEBAR, BG_TOOLBAR, BG_URLBAR, FG_DIM, FG_TEXT


class TabBar(tk.Frame):
    """Tab strip: one clickable/closable header per open tab plus a + button."""

    def __init__(self, master: tk.Misc, on_new=None) -> None:
        super().__init__(master, bg=BG_TITLEBAR)
        self.on_new = on_new or (lambda: None)
        self.headers: list[tk.Frame] = []
        self._build()

    def _build(self) -> None:
        """Create the persistent new-tab button."""
        self.new_btn = tk.Label(
            self, text=" + ", font=("Segoe UI", 11),
            bg=BG_TITLEBAR, fg=FG_DIM, cursor="hand2",
            padx=6, pady=4,
        )
        self.new_btn.bind("<Button-1>", lambda e: self.on_new())
        self._reflow()

    def _reflow(self) -> None:
        """Re-pack headers in order, keeping the + button at the end."""
        self.new_btn.pack_forget()
        for header in self.headers:
            header.pack_forget()
        for header in self.headers:
            header.pack(side="left", padx=(2, 0), pady=(4, 0))
        self.new_btn.pack(side="left", padx=(2, 0))

    def add_header(self, title: str, on_select, on_close) -> tk.Frame:
        """Create a tab header (title + close button) and return it."""
        header = tk.Frame(self, bg=BG_TAB_ACTIVE)
        title_lbl = tk.Label(
            header, text=self._clip(title), font=("Segoe UI", 10),
            bg=BG_TAB_ACTIVE, fg=FG_TEXT, padx=10, pady=6, cursor="hand2",
        )
        title_lbl.pack(side="left")
        close_lbl = tk.Label(
            header, text="✕", font=("Segoe UI", 9),
            bg=BG_TAB_ACTIVE, fg=FG_DIM, padx=4, pady=6, cursor="hand2",
        )
        close_lbl.pack(side="left")

        # Click anywhere on the title selects; the ✕ closes.
        title_lbl.bind("<Button-1>", lambda e: on_select())
        header.bind("<Button-1>", lambda e: on_select())
        close_lbl.bind("<Button-1>", lambda e: on_close())

        # Remember sub-widgets for restyling / retitling.
        header._title_lbl = title_lbl
        header._close_lbl = close_lbl

        self.headers.append(header)
        self._reflow()
        return header

    def remove_header(self, header: tk.Frame) -> None:
        """Detach and destroy a tab header."""
        if header in self.headers:
            self.headers.remove(header)
        try:
            header.destroy()
        except Exception:
            pass
        self._reflow()

    def set_active(self, index: int) -> None:
        """Highlight the active header; dim the rest."""
        for i, header in enumerate(self.headers):
            active = (i == index)
            bg = BG_TAB_ACTIVE if active else BG_TAB
            fg = FG_TEXT if active else FG_DIM
            try:
                header.configure(bg=bg)
                header._title_lbl.configure(bg=bg, fg=fg)
                header._close_lbl.configure(bg=bg)
            except Exception:
                pass

    def set_title(self, header: tk.Frame, title: str) -> None:
        """Update a header's displayed title."""
        if header is not None and header._title_lbl.winfo_exists():
            header._title_lbl.configure(text=self._clip(title))

    @staticmethod
    def _clip(title: str, limit: int = 22) -> str:
        title = (title or "").strip() or "New Tab"
        return title if len(title) <= limit else title[: limit - 1] + "…"


class Toolbar(tk.Frame):
    """Navigation buttons + URL / search bar."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, bg=BG_TOOLBAR)
        # Callbacks wired by BrowserWindow.
        self.on_navigate = lambda text: None
        self.on_back = lambda: None
        self.on_forward = lambda: None
        self.on_reload = lambda: None
        self._build()

    def _build(self) -> None:
        """Construct the toolbar controls and search entry."""
        btn_cfg = dict(
            font=("Segoe UI", 13), bg=BG_TOOLBAR, fg=FG_DIM,
            bd=0, padx=6, pady=2, cursor="hand2",
            activebackground=BG_TOOLBAR, activeforeground=FG_TEXT,
        )
        self.back_btn = tk.Button(self, text="←", command=lambda: self.on_back(), **btn_cfg)
        self.back_btn.pack(side="left", padx=2)

        self.forward_btn = tk.Button(self, text="→", command=lambda: self.on_forward(), **btn_cfg)
        self.forward_btn.pack(side="left", padx=2)

        self.reload_btn = tk.Button(self, text="⟳", command=lambda: self.on_reload(), **btn_cfg)
        self.reload_btn.pack(side="left", padx=2)

        # Back/forward start disabled; updated per active tab via set_nav_state.
        self.back_btn.config(state="disabled")
        self.forward_btn.config(state="disabled")

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

        def _on_focus_in(e: tk.Event) -> None:
            if entry.get() == placeholder:
                entry.delete(0, "end")
                entry.config(fg=FG_TEXT)

        def _on_focus_out(e: tk.Event) -> None:
            if not entry.get():
                entry.insert(0, placeholder)
                entry.config(fg=FG_DIM)

        entry.bind("<FocusIn>", _on_focus_in)
        entry.bind("<FocusOut>", _on_focus_out)
        entry.bind("<Return>", lambda e: self.on_navigate(entry.get()))
        self.entry = entry
        self.placeholder = placeholder

    def set_nav_state(self, can_back: bool, can_forward: bool) -> None:
        """Enable/disable the back and forward buttons for the active tab."""
        self.back_btn.config(state="normal" if can_back else "disabled")
        self.forward_btn.config(state="normal" if can_forward else "disabled")

    def focus_address_bar(self) -> None:
        """Focus the URL bar and select its contents (Ctrl+L)."""
        entry = self.entry
        entry.configure(state="normal")
        if entry.get() == self.placeholder:
            entry.delete(0, "end")
            entry.config(fg=FG_TEXT)
        entry.focus_set()
        entry.select_range(0, "end")
        entry.icursor("end")
