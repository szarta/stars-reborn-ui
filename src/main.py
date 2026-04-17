"""
main.py

Entry point for Stars Reborn.
"""

import argparse
import logging
import sys

from ._version import __version__

default_log_format = "%(filename)s:%(levelname)s:%(asctime)s] %(message)s"


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="stars-reborn", description="Stars Reborn — a faithful clone of Stars! (1995)"
    )
    parser.add_argument("-v", "--verbose", help="increase output verbosity", action="store_true")
    parser.add_argument(
        "--version", action="version", version=__version__, help="show the version and exit"
    )
    parser.add_argument("--no-gui", help="run in headless mode (for testing)", action="store_true")
    parser.add_argument(
        "--engine-url",
        default="http://localhost:8080",
        metavar="URL",
        help="base URL of the Stars Reborn engine (default: http://localhost:8080)",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(format=default_log_format)
    logging.getLogger().setLevel(logging.DEBUG if args.verbose else logging.INFO)

    if args.no_gui:
        logging.info("Headless mode — exiting")
        return 0

    try:
        import PySide6  # noqa: F401
    except ImportError:
        print("PySide6 is required.  Install with: pip install PySide6")
        return 1

    from .data.loader import load_language_map
    from .rendering.enumerations import ResourcePaths
    from .ui.app import create_app
    from .ui.intro import IntroUI

    app = create_app(sys.argv)
    load_language_map(ResourcePaths.EnglishLanguageMap)

    window = IntroUI(engine_url=args.engine_url)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
