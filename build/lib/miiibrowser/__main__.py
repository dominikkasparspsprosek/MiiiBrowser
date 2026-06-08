try:
    from .BrowserWindow import BrowserWindow
except ImportError:  # allow `python BrowserWindow.py`-style loose runs
    from BrowserWindow import BrowserWindow


def main() -> None:
    """Create the browser window and enter the Tk event loop."""
    app = BrowserWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
