from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv

from path_config import get_scraped_output_dir

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
REQUEST_HEADERS = {
    "User-Agent": "agentic-rag/0.1 (local-dev-script)",
}


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def configure_tls_from_system_store() -> None:
    try:
        import truststore

        truststore.inject_into_ssl()
    except Exception:
        # Keep running with certifi defaults if truststore is unavailable.
        pass


def search_wikipedia_title(subject: str, *, allow_insecure: bool) -> str:
    params = {
        "action": "opensearch",
        "search": subject,
        "limit": 1,
        "namespace": 0,
        "format": "json",
    }
    response = requests.get(
        WIKIPEDIA_API,
        params=params,
        headers=REQUEST_HEADERS,
        timeout=20,
        verify=not allow_insecure,
    )
    response.raise_for_status()
    payload = response.json()

    titles = payload[1] if len(payload) > 1 else []
    if not titles:
        raise ValueError(f"No Wikipedia article found for subject: {subject}")

    return titles[0]


def fetch_page_extract(title: str, *, allow_insecure: bool) -> tuple[str, str]:
    params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": 1,
        "redirects": 1,
        "titles": title,
        "format": "json",
        "formatversion": 2,
    }
    response = requests.get(
        WIKIPEDIA_API,
        params=params,
        headers=REQUEST_HEADERS,
        timeout=20,
        verify=not allow_insecure,
    )
    response.raise_for_status()
    payload = response.json()

    pages = payload.get("query", {}).get("pages", [])
    if not pages:
        raise ValueError(f"No page content returned for title: {title}")

    page = pages[0]
    if page.get("missing"):
        raise ValueError(f"Wikipedia page is missing for title: {title}")

    extract = (page.get("extract") or "").strip()
    if not extract:
        raise ValueError(f"Wikipedia page has no extract text for title: {title}")

    resolved_title = page.get("title", title)
    return resolved_title, extract


def to_safe_filename(value: str) -> str:
    normalized = value.strip().replace(" ", "_")
    safe = re.sub(r"[\\/:*?\"<>|]", "_", normalized)
    return safe or "wikipedia_page"


def parse_subjects(value: str) -> list[str]:
    raw_items = [item.strip() for item in value.split(",")]
    subjects = [item for item in raw_items if item]

    # Keep insertion order while removing duplicates.
    unique_subjects: list[str] = []
    seen: set[str] = set()
    for subject in subjects:
        lowered = subject.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique_subjects.append(subject)
    return unique_subjects


def get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise SystemExit(f"Invalid integer for {name}: {value}") from exc


def clear_scraped_text_files(directory: Path) -> None:
    for path in directory.glob("*.txt"):
        path.unlink()


def scrape_subject(subject: str, *, allow_insecure: bool, output_dir: Path) -> dict:
    try:
        best_title = search_wikipedia_title(subject, allow_insecure=allow_insecure)
        resolved_title, extract = fetch_page_extract(
            best_title, allow_insecure=allow_insecure
        )
        output_path = output_dir / f"{to_safe_filename(resolved_title)}.txt"
        output_path.write_text(extract, encoding="utf-8")
    except requests.RequestException as exc:
        return {
            "subject": subject,
            "success": False,
            "error": f"Network/API error while contacting Wikipedia: {exc}",
        }
    except (ValueError, OSError) as exc:
        return {"subject": subject, "success": False, "error": str(exc)}

    page_url = (
        f"https://en.wikipedia.org/wiki/{quote(resolved_title.replace(' ', '_'))}"
    )
    return {
        "subject": subject,
        "success": True,
        "resolved_title": resolved_title,
        "url": page_url,
        "output_path": str(output_path),
    }


def main() -> None:
    load_dotenv()
    configure_tls_from_system_store()

    subject_value = (os.getenv("WIKI_SUBJECT") or "").strip()
    allow_insecure = env_flag("WIKI_ALLOW_INSECURE", default=False)

    subjects = parse_subjects(subject_value)
    if not subjects:
        raise SystemExit(
            "Missing WIKI_SUBJECT in .env (example: WIKI_SUBJECT=AI,Machine learning)"
        )
    max_workers = get_env_int("WIKI_MAX_WORKERS", min(4, len(subjects)))
    if max_workers <= 0:
        raise SystemExit("WIKI_MAX_WORKERS must be greater than 0")
    max_workers = min(max_workers, len(subjects))

    output_dir = get_scraped_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    clear_scraped_text_files(output_dir)

    print(
        f"Parallel scraping started for {len(subjects)} subjects (workers={max_workers})."
    )

    results_by_subject: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(
                scrape_subject,
                subject,
                allow_insecure=allow_insecure,
                output_dir=output_dir,
            )
            for subject in subjects
        ]
        for future in as_completed(futures):
            result = future.result()
            results_by_subject[result["subject"]] = result

    success_count = 0
    failed_subjects: list[str] = []
    for subject in subjects:
        result = results_by_subject[subject]
        if not result["success"]:
            print(f"Subject: {subject}")
            print(f"Error: {result['error']}")
            failed_subjects.append(subject)
            continue

        print(f"Subject: {subject}")
        print(f"Resolved page: {result['resolved_title']}")
        print(f"URL: {result['url']}")
        print(f"Saved text to: {result['output_path']}")
        success_count += 1

    print(f"Scrape summary: {success_count} succeeded, {len(failed_subjects)} failed.")
    if failed_subjects:
        failed_display = ", ".join(failed_subjects)
        raise SystemExit(f"Failed subjects: {failed_display}")


if __name__ == "__main__":
    main()
