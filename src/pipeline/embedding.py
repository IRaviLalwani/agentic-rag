from __future__ import annotations

import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from logger import get_logger

from path_config import get_chunk_output_file, get_embedding_output_file


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Chunk file not found: {path}. Run chunk.py first.")

    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in records:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def embed_text(base_url: str, model: str, text: str) -> list[float]:
    embed_url = f"{base_url}/api/embed"
    response = requests.post(
        embed_url, json={"model": model, "input": text}, timeout=60
    )

    if response.status_code == 404:
        legacy_url = f"{base_url}/api/embeddings"
        legacy_response = requests.post(
            legacy_url,
            json={"model": model, "prompt": text},
            timeout=60,
        )
        legacy_response.raise_for_status()
        legacy_payload = legacy_response.json()
        vector = legacy_payload.get("embedding")
        if not isinstance(vector, list):
            raise RuntimeError("Unexpected embedding response from /api/embeddings")
        return vector

    response.raise_for_status()
    payload = response.json()
    embeddings = payload.get("embeddings")
    if not isinstance(embeddings, list) or not embeddings:
        raise RuntimeError("Unexpected embedding response from /api/embed")

    vector = embeddings[0]
    if not isinstance(vector, list):
        raise RuntimeError("Unexpected embedding vector shape from /api/embed")

    return vector


def run() -> Path:
    logger = get_logger("pipeline.embedding")
    logger.info("Embedding process is starting.")

    load_dotenv()

    chunk_file = get_chunk_output_file()
    output_file = get_embedding_output_file()
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    selected_model = (os.getenv("OLLAMA_EMBED_MODEL") or "").strip()
    if not selected_model:
        raise RuntimeError("Missing OLLAMA_EMBED_MODEL in .env")

    chunks = read_jsonl(chunk_file)
    logger.info("Embedding process is going on for %d chunks.", len(chunks))
    logger.info("Using configured embedding model: %s", selected_model)

    records: list[dict] = []
    for idx, row in enumerate(chunks, start=1):
        text = row.get("text", "")
        if not text:
            continue

        vector = embed_text(base_url, selected_model, text)

        records.append(
            {
                "chunk_id": row["chunk_id"],
                "chunk_index": row["chunk_index"],
                "source_file": row["source_file"],
                "text": text,
                "embedding": vector,
                "embedding_dim": len(vector),
                "model": selected_model,
            }
        )

        if idx % 10 == 0 or idx == len(chunks):
            logger.info("Embedding progress: %d/%d", idx, len(chunks))

    write_jsonl(output_file, records)

    logger.info("Embedding completed. Total embedding records: %d", len(records))
    logger.info("Embedding file written at: %s", output_file)
    return output_file


def main() -> None:
    logger = get_logger("pipeline.embedding")
    try:
        run()
    except Exception as exc:
        logger.error("Embedding failed: %s", exc, exc_info=True)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
