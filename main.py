from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SCRAPER_SCRIPT = ROOT / "src" / "scraper" / "scraper.py"
PIPELINE_SCRIPT = ROOT / "src" / "pipeline" / "main.py"
CHATBOT_SCRIPT = ROOT / "src" / "chatbot" / "chatbot.py"


def run_script(script_path: Path) -> None:
    script_dir = str(script_path.parent.resolve())
    src_dir = str(ROOT.joinpath("src").resolve())
    inserted: list[str] = []
    for candidate in (script_dir, src_dir):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)
            inserted.append(candidate)
    try:
        runpy.run_path(str(script_path), run_name="__main__")
    finally:
        for candidate in reversed(inserted):
            if candidate in sys.path:
                sys.path.remove(candidate)


def main() -> None:
    parser = argparse.ArgumentParser(description="Agentic-RAG product entrypoint")
    parser.add_argument(
        "command",
        nargs="?",
        default="scrape",
        choices=["scrape", "pipeline", "chatbot", "build"],
        help="scrape | pipeline | chatbot | build (scrape + pipeline)",
    )
    args = parser.parse_args()

    if args.command == "scrape":
        run_script(SCRAPER_SCRIPT)
    elif args.command == "pipeline":
        run_script(PIPELINE_SCRIPT)
    elif args.command == "chatbot":
        run_script(CHATBOT_SCRIPT)
    elif args.command == "build":
        run_script(SCRAPER_SCRIPT)
        run_script(PIPELINE_SCRIPT)
    else:
        raise SystemExit(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
