from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from logger import get_logger

from path_config import get_chunk_output_file, get_scraped_output_dir


def get_env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Invalid integer for {name}: {value}") from exc


def resolve_source_files() -> list[Path]:
    scraped_dir = get_scraped_output_dir()
    txt_files = sorted(scraped_dir.glob("*.txt"))
    if not txt_files:
        raise FileNotFoundError(
            f"No scraped txt files found in {scraped_dir}/. Run scraper first."
        )
    return txt_files


def split_paragraphs(text: str) -> list[str]:
    parts = [p.strip() for p in text.split("\n\n")]
    return [p for p in parts if p]


def make_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("CHUNK_SIZE must be greater than 0")
    if overlap < 0:
        raise ValueError("CHUNK_OVERLAP cannot be negative")
    if overlap >= chunk_size:
        raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE")

    paragraphs = split_paragraphs(text)
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)

            if overlap > 0:
                carry = current[-overlap:]
                current = f"{carry}\n\n{paragraph}"
            else:
                current = paragraph

            while len(current) > chunk_size:
                chunks.append(current[:chunk_size])
                if overlap > 0:
                    current = current[chunk_size - overlap :]
                else:
                    current = current[chunk_size:]
        else:
            tmp = paragraph
            while len(tmp) > chunk_size:
                chunks.append(tmp[:chunk_size])
                if overlap > 0:
                    tmp = tmp[chunk_size - overlap :]
                else:
                    tmp = tmp[chunk_size:]
            current = tmp

    if current.strip():
        chunks.append(current)

    return [c.strip() for c in chunks if c.strip()]


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in records:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def run() -> Path:
    logger = get_logger("pipeline.chunk")
    logger.info("Chunking process is starting.")

    load_dotenv()

    source_files = resolve_source_files()
    output_file = get_chunk_output_file()
    chunk_size = get_env_int("CHUNK_SIZE", 1200)
    overlap = get_env_int("CHUNK_OVERLAP", 200)

    records: list[dict] = []
    for source_file in source_files:
        logger.info("Chunking process is going on for source file: %s", source_file)
        text = source_file.read_text(encoding="utf-8")
        chunks = make_chunks(text, chunk_size=chunk_size, overlap=overlap)

        file_key = hashlib.sha1(str(source_file.resolve()).encode("utf-8")).hexdigest()[
            :8
        ]
        file_records = [
            {
                "chunk_id": f"{source_file.stem}-{file_key}-{idx:04d}",
                "chunk_index": idx,
                "source_file": str(source_file),
                "text": chunk,
            }
            for idx, chunk in enumerate(chunks)
        ]
        records.extend(file_records)
        logger.info(
            "Chunking completed for file %s with %d chunks.",
            source_file,
            len(file_records),
        )

    write_jsonl(output_file, records)

    logger.info("Total source files processed: %d", len(source_files))
    logger.info("Chunking completed. Total chunks: %d", len(records))
    logger.info("Chunk file written at: %s", output_file)
    return output_file


def main() -> None:
    logger = get_logger("pipeline.chunk")
    try:
        run()
    except Exception as exc:
        logger.error("Chunking failed: %s", exc, exc_info=True)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
