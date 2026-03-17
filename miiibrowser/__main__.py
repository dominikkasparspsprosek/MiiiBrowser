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
        pass 


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

        # text style tags
        self.output.tag_configure("h1",      font=("Segoe UI", 22, "bold"),  foreground=FG_TEXT)
        self.output.tag_configure("h2",      font=("Segoe UI", 13, "bold"),  foreground=FG_TEXT)
        self.output.tag_configure("section", font=("Segoe UI", 11, "bold"),  foreground=ACCENT)
        self.output.tag_configure("body",    font=("Segoe UI", 10),          foreground=FG_TEXT)
        self.output.tag_configure("dim",     font=("Segoe UI", 9),           foreground=FG_DIM)
        self.output.tag_configure("link",    font=("Segoe UI", 9),           foreground=ACCENT)
        self.output.tag_configure("divider", foreground="#3c4043")
        self._link_counter = 0

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

    def _fetch_url(self, url: str):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MiiiBrowser/0.1"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                base_url = resp.url  # final URL after redirects
                raw = resp.read().decode("utf-8", errors="replace")

            # ── extract and strip <head> ──────────────────────────
            head_match = re.search(r"<head[^>]*>(.*?)</head>", raw, re.IGNORECASE | re.DOTALL)
            self.head = head_match.group(1) if head_match else ""
            body = raw[head_match.end():] if head_match else raw  # everything after </head>

            # ── title ─────────────────────────────────────────────
            titles = re.findall(r"<title[^>]*>(.*?)</title>", self.head, re.IGNORECASE | re.DOTALL)
            tab_title = titles[0].strip() if len(titles) == 1 else "document"

            # ── stylesheets: inline <style> blocks ────────────────
            self.stylesheets: dict[str, str] = {}
            for i, css in enumerate(re.findall(
                r"<style[^>]*>(.*?)</style>", self.head, re.IGNORECASE | re.DOTALL
            )):
                self.stylesheets[f"inline_{i}"] = css.strip()

            # ── stylesheets: external <link rel="stylesheet"> ─────
            for link_tag in re.findall(r"<link[^>]+>", self.head, re.IGNORECASE):
                if re.search(r'rel=["\']stylesheet["\']', link_tag, re.IGNORECASE):
                    href_m = re.search(r'href=["\']([^"\']+)["\']', link_tag, re.IGNORECASE)
                    if href_m:
                        href = href_m.group(1)
                        # resolve relative URLs
                        sheet_url = urllib.parse.urljoin(base_url, href)
                        sheet_name = href.split("/")[-1].split("?")[0] or href
                        try:
                            sheet_req = urllib.request.Request(
                                sheet_url, headers={"User-Agent": "MiiiBrowser/0.1"}
                            )
                            with urllib.request.urlopen(sheet_req, timeout=8) as sr:
                                self.stylesheets[sheet_name] = sr.read().decode("utf-8", errors="replace")
                        except Exception:
                            self.stylesheets[sheet_name] = ""  # failed to fetch

        except Exception as exc:
            body = f"Error: {exc}"
            tab_title = "document"
            self.head = ""
            self.stylesheets = {}

        self.after(0, self._set_plain, body)
        self.after(0, self._set_tab_title, tab_title)

    def _fetch_ddg(self, query: str):
        try:
            params = urllib.parse.urlencode({"q": query, "format": "json", "no_html": "1"})
            url = f"https://api.duckduckgo.com/?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "MiiiBrowser/0.1"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as exc:
            self.after(0, self._set_plain, f"Error: {exc}")
            return

        # find the first usable URL: direct results first, then related topics
        first_url = None
        for item in data.get("Results", []):
            if item.get("FirstURL"):
                first_url = item["FirstURL"]
                break
        if not first_url:
            for item in data.get("RelatedTopics", []):
                if item.get("FirstURL"):
                    first_url = item["FirstURL"]
                    break
                for sub in item.get("Topics", []):
                    if sub.get("FirstURL"):
                        first_url = sub["FirstURL"]
                        break
                if first_url:
                    break

        if first_url:
            self.after(0, self._navigate, first_url)
        else:
            self.after(0, self._set_plain, "No results found.")

    def _set_tab_title(self, title: str):
        if self.tab_bar.tabs:
            self.tab_bar.tabs[0].configure(text=f"  {title}  ")

    def _insert_link(self, text: str, url: str):
        t = self.output
        tag = f"_link_{self._link_counter}"
        self._link_counter += 1
        t.tag_configure(tag, font=("Segoe UI", 9), foreground=ACCENT, underline=True)
        t.tag_bind(tag, "<Enter>",  lambda e: t.configure(cursor="hand2"))
        t.tag_bind(tag, "<Leave>",  lambda e: t.configure(cursor=""))
        t.tag_bind(tag, "<Button-1>", lambda e, u=url: self._navigate(u))
        t.insert("end", text, (tag,))

    def _set_plain(self, text: str):
        t = self.output
        t.configure(state="normal")
        t.delete("1.0", "end")
        t.insert("end", text, "body")
        t.configure(state="disabled")

    def _render_ddg(self, d: dict):
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


def main():
    app = BrowserWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
