"""Console entry point for starting MiiiBrowser."""

if __package__ in {None, ""}:
    import os
    import sys

    package_dir = os.path.dirname(os.path.abspath(__file__))
    if package_dir not in sys.path:
        sys.path.insert(0, package_dir)
    from BrowserWindow import BrowserWindow
else:
    from .BrowserWindow import BrowserWindow


def main() -> None:
    """Create the browser window and enter the Tk event loop."""
    app = BrowserWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
