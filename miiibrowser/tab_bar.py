"""Tab bar and toolbar widgets for the MiiiBrowser window."""

import tkinter as tk

try:
    from .colors import ACCENT, BG_TAB_ACTIVE, BG_TITLEBAR, BG_TOOLBAR, BG_URLBAR, FG_DIM, FG_TEXT
except ImportError:
    from colors import ACCENT, BG_TAB_ACTIVE, BG_TITLEBAR, BG_TOOLBAR, BG_URLBAR, FG_DIM, FG_TEXT


class TabBar(tk.Frame):
    """Simple tab strip with a single active tab and a new-tab button."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, bg=BG_TITLEBAR)
        self.tabs: list[tk.Label] = []
        self._build()

    def _build(self) -> None:
        """Construct the initial tab strip widgets."""
        # one default tab
        self._add_tab("New Tab")

        # '+' button
        self.new_btn = tk.Label(
            self, text=" + ", font=("Segoe UI", 11),
            bg=BG_TITLEBAR, fg=FG_DIM, cursor="hand2",
            padx=6, pady=4,
        )
        self.new_btn.pack(side="left", padx=(2, 0))

    def _add_tab(self, title: str) -> None:
        """Create and store a tab label for the given title."""
        tab = tk.Label(
            self, text=f"  {title}  ", font=("Segoe UI", 10),
            bg=BG_TAB_ACTIVE, fg=FG_TEXT,
            padx=12, pady=6, relief="flat",
        )
        tab.pack(side="left", padx=(2, 0), pady=(4, 0))
        self.tabs.append(tab)


class Toolbar(tk.Frame):
    """Navigation buttons + URL / search bar."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, bg=BG_TOOLBAR)
        self._build()

    def _build(self) -> None:
        """Construct the toolbar controls and search entry."""
        btn_cfg = dict(
            font=("Segoe UI", 13), bg=BG_TOOLBAR, fg=FG_DIM,
            bd=0, padx=6, pady=2, cursor="hand2",
            activebackground=BG_TOOLBAR, activeforeground=FG_TEXT,
        )
        # back / forward / reload
        self.on_back = lambda: None
        self.on_forward = lambda: None
        self.on_reload = lambda: None

        self.back_btn = tk.Button(self, text="←", command=lambda: self.on_back(), **btn_cfg)
        self.back_btn.pack(side="left", padx=2)

        self.forward_btn = tk.Button(self, text="→", command=lambda: self.on_forward(), **btn_cfg)
        self.forward_btn.pack(side="left", padx=2)

        self.reload_btn = tk.Button(self, text="⟳", command=lambda: self.on_reload(), **btn_cfg)
        self.reload_btn.pack(side="left", padx=2)

        # start disabled
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

    def on_navigate(self, text: str) -> None:
        """Callback invoked when the user submits the URL/search field."""
        pass

