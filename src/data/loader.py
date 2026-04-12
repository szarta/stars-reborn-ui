"""
data/loader.py

Loaders for UI-side resource files (language strings, etc.).

Technology and game data will be fetched from the engine HTTP API.  The
language map is the only file loaded directly from disk here.
"""

import json
import logging

log = logging.getLogger(__name__)

# UI string map, populated by load_language_map().
# Callers use: Language_Map.get("ui", {}).get("general", {}).get("key", "default")
Language_Map: dict = {}


def load_language_map(path: str) -> None:
    """Load the UI string map from a JSON file.  Falls back silently to empty map."""
    global Language_Map
    try:
        with open(path, encoding="utf-8") as f:
            Language_Map = json.load(f)
    except FileNotFoundError:
        log.debug("Language map not found at %s — using built-in defaults", path)
    except Exception as exc:
        log.warning("Failed to load language map from %s: %s", path, exc)
