# MiiiBrowser

A Chrome-style Python desktop browser with web viewing and tabbed interface. Features DuckDuckGo search integration and full browsing capabilities.

## WIP features

- **DuckDuckGo Search**: Direct search integration with automatic redirect handling
- **Chrome-Style Tabs**: Multiple independent tabs with easy switching
- **Embedded Web Viewer**: Browse websites directly within the app using tkinterweb
- **Full Image Support**: Display JPG, PNG, SVG, and other image formats
- **Navigation Controls**: Back, forward, and reload buttons with history tracking
- **Smart URL Handling**: Automatic detection of URLs vs search queries
- **Modern UI**: Clean, Google-inspired design with intuitive controls
- **Fullscreen Mode**: Toggle fullscreen with F11 or the fullscreen button
- **Link Navigation**: Click links within pages to navigate seamlessly
- **Keyboard Shortcuts**: Quick access to common functions
- **CSS Parser**: Full CSS3 parsing with tinycss2 for stylesheet analysis

## Documentation

To generate the HTML documentation with Sphinx in this repository, run:

```powershell
pip install .[docs]
sphinx-apidoc -o docs_template miiibrowser --full --force
sphinx-build docs_template docs
```

Notes:

- `miiibrowser` is the package folder for this project, so you do not need `src` in the command.
- `sphinx-apidoc` generates the Sphinx source files into `docs_template`.
- `sphinx-build` converts those files into HTML output in `docs`.
- If you add more Python subfolders later, add an `__init__.py` file to each one so Sphinx treats them as modules.
