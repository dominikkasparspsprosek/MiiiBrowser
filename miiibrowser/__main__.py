import tkinter as tk
from tkinter import ttk


# ── colour palette (Chrome-inspired) ──────────────────────────────
BG_TITLEBAR  = "#202124"
BG_TAB       = "#35363a"
BG_TAB_ACTIVE = "#292a2d"
BG_TOOLBAR   = "#292a2d"
FG_TEXT       = "#e8eaed"
FG_DIM        = "#9aa0a6"
BG_URLBAR     = "#202124"
ACCENT        = "#8ab4f8"


class TabBar(tk.Frame):
    """Row of fake tabs + a '+' new-tab button."""

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
        # back / forward / reload / home
        for symbol in ("←", "→", "⟳", "⌂"):
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

        # extra buttons (extensions / profile placeholders)
        for symbol in ("⋮",):
            tk.Button(self, text=symbol, **btn_cfg).pack(side="right", padx=2)


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

        # content area (blank page)
        self.content = tk.Frame(self, bg="#202124")
        self.content.pack(fill="both", expand=True)

        # centered "New Tab" label like Chrome's blank page
        tk.Label(
            self.content, text="MiiiBrowser", font=("Segoe UI", 28, "bold"),
            bg="#202124", fg=FG_DIM,
        ).place(relx=0.5, rely=0.38, anchor="center")


def main():
    app = BrowserWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
