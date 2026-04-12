# stars-reborn-ui

Python / PySide6 game client for [Stars Reborn](https://github.com/szarta/stars-reborn-game) —
a faithful open-source reimplementation of Stars! (1995).

## Overview

This is the view layer only.  All game logic lives in
[stars-reborn-engine](https://github.com/szarta/stars-reborn-engine), a Rust HTTP
server.  The UI communicates with the engine exclusively over HTTP — no shared
libraries, no PyO3 bindings.

**Single-player:** a thin launcher starts the engine on localhost, opens the client,
and shuts the engine down on exit.

**Multiplayer:** the client points at a remote host — zero code changes required.

## Game flow

1. **New Game** — UI sends `POST /game/new` to the engine; receives initial turn
   files; writes them to the configured game folder; opens the turn editor on the
   player's `.m` (JSON) file.
2. **Turn editing** — player makes orders; changes are saved locally to their `.xy`
   (JSON) file.
3. **Turn generation** — player submits orders (`POST /game/{id}/player/{n}/orders`);
   UI polls `GET /game/{id}/turn/status` until the new turn is ready; retrieves the
   updated `.m` files.
4. **Multiplayer / host** — the host admin view shows submission status, allows
   skipping absent players, and triggers generation once all humans have submitted.
   Same HTTP flow; the engine handles the waiting.

## Tech stack

- Python 3.11+
- PySide6 (Qt6) — QPainter rendering, no WebView
- `requests` for HTTP communication with the engine
- SVG for the space map; PNG for raster assets; programmatic generation for graphs
  and resource bars

## Repository layout

```
assets/
  xcf/        GIMP source files (editing format — not loaded by the app)
  png/        Exported raster assets loaded at runtime
  svg/        Vector assets (space map overlays, UI chrome)
  final/      Qt resource bundle staging (.qrc)
reference/    Research notes and legacy code (gitignored)
src/
  main.py             Entry point
  _version.py
  data/               UI-side resource loaders (language strings, etc.)
  rendering/          Local rendering constants and helpers
    enumerations.py   ResourcePaths, PlanetView, ZoomLevel, PrimaryRacialTrait
    space.py          Habitat normalization (gravity / temperature → 0-100 scale)
  ui/                 PySide6 widgets and dialogs
    app.py            QApplication setup (Win95 Fusion palette)
    intro.py          Entry screen (New Game / Load Game / Host Game / Race Editor / About / Exit)
    main_window.py    Primary game window (space map + info panel + toolbar)
    space_map.py      QPainter star map widget
    info_panel.py     Right-dock planet/fleet detail panel
    dialogs/
      planet.py       Planet detail dialog (hab bars, population, infrastructure)
```

## Development setup

```bash
pip install -r requirements-dev.txt
pre-commit install
```

Pre-commit hooks: trailing whitespace, end-of-file, YAML check, ruff (lint + format),
xenon (complexity — blocks on rank D or worse).

## Image assets

Original Stars! bitmap assets are not used.  All art is created from scratch to allow
free use, modification, and repackaging by the community.

- `.xcf` files are the authoritative editing sources (GIMP, with layers and history).
- `.png` files are exported from GIMP and checked in alongside their source.
- `.svg` files are used for the space map and scalable UI elements.

## License

MIT — see `LICENSE.txt`.
