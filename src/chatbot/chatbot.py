from __future__ import annotations

import json
import logging
import math
import os
import sqlite3
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

from path_config import get_ingest_db_path

LOG_DIR = Path("logs")
ERROR_LOG_FILE = LOG_DIR / "errorlogs.txt"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def get_logger() -> logging.Logger:
    logger = logging.getLogger("chatbot")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(LOG_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    error_file_handler = logging.FileHandler(ERROR_LOG_FILE, encoding="utf-8")
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(error_file_handler)
    return logger


def read_ingested_rows(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.exists():
        raise FileNotFoundError(f"Ingest DB not found: {db_path}")

    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.execute(
            """
            SELECT chunk_id, source_file, text, embedding_json, model
            FROM chunks
            ORDER BY chunk_index ASC
            """
        )
        rows = cursor.fetchall()
    finally:
        connection.close()

    if not rows:
        raise ValueError(f"No records found in ingest DB: {db_path}")

    parsed: list[dict[str, Any]] = []
    for chunk_id, source_file, text, embedding_json, model in rows:
        try:
            embedding = json.loads(embedding_json)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid embedding_json for chunk_id={chunk_id}") from exc

        if not isinstance(embedding, list):
            raise ValueError(f"Invalid embedding list for chunk_id={chunk_id}")

        parsed.append(
            {
                "chunk_id": chunk_id,
                "source_file": source_file,
                "text": text,
                "embedding": embedding,
                "model": model,
            }
        )

    return parsed


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return -1.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return -1.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def embed_text(base_url: str, model: str, text: str) -> list[float]:
    response = requests.post(
        f"{base_url}/api/embed",
        json={"model": model, "input": text},
        timeout=60,
    )

    if response.status_code == 404:
        legacy = requests.post(
            f"{base_url}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=60,
        )
        legacy.raise_for_status()
        payload = legacy.json()
        vector = payload.get("embedding")
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
        raise RuntimeError("Unexpected embedding vector shape")
    return vector


def retrieve_context(
    query_embedding: list[float],
    records: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    for row in records:
        embedding = row.get("embedding")
        if not isinstance(embedding, list):
            continue
        score = cosine_similarity(query_embedding, embedding)
        scored.append(
            {
                "score": score,
                "chunk_id": row.get("chunk_id", ""),
                "text": row.get("text", ""),
                "source_file": row.get("source_file", ""),
            }
        )

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]


def generate_answer(
    base_url: str,
    model: str,
    question: str,
    context_rows: list[dict[str, Any]],
    max_context_chars: int,
    request_timeout: int,
) -> str:
    context_parts: list[str] = []
    running_length = 0
    for idx, row in enumerate(context_rows):
        part = f"[{idx + 1}] {row['text']}"
        next_len = running_length + len(part) + 2
        if context_parts and next_len > max_context_chars:
            break
        context_parts.append(part)
        running_length = next_len
    context_text = "\n\n".join(context_parts)

    prompt = (
        "You are a strict RAG assistant.\n"
        "Answer ONLY from the CONTEXT below.\n"
        "If the answer is not in the context, reply exactly:\n"
        "I do not have enough information in the provided context.\n\n"
        f"CONTEXT:\n{context_text}\n\n"
        f"QUESTION: {question}\n"
        "ANSWER (brief and accurate):"
    )

    response = requests.post(
        f"{base_url}/api/generate",
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": 220},
        },
        timeout=request_timeout,
    )
    response.raise_for_status()
    payload = response.json()
    answer = payload.get("response", "")
    if not isinstance(answer, str):
        raise RuntimeError("Unexpected response from /api/generate")
    return answer.strip()


def parse_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Invalid integer for {name}: {value}") from exc


def parse_float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Invalid float for {name}: {value}") from exc


def main() -> None:
    logger = get_logger()
    try:
        load_dotenv()

        base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        db_path = get_ingest_db_path()
        top_k = parse_int_env("CHAT_TOP_K", 4)
        min_similarity = parse_float_env("CHAT_MIN_SIMILARITY", 0.15)
        max_context_chars = parse_int_env("CHAT_MAX_CONTEXT_CHARS", 3600)
        request_timeout = parse_int_env("CHAT_REQUEST_TIMEOUT", 300)

        records = read_ingested_rows(db_path)

        embed_model = (os.getenv("OLLAMA_EMBED_MODEL") or "").strip() or str(
            records[0].get("model", "")
        )
        if not embed_model:
            raise RuntimeError("Embedding model is missing. Set OLLAMA_EMBED_MODEL.")

        chat_model = (os.getenv("OLLAMA_CHAT_MODEL") or "").strip()
        if not chat_model:
            raise RuntimeError("Missing OLLAMA_CHAT_MODEL in .env")

        logger.info("Chatbot started with chat model: %s", chat_model)
        logger.info("Using embedding model: %s", embed_model)
        logger.info(
            "Loaded %d embedded chunks from ingest DB: %s", len(records), db_path
        )
        print("Type 'exit' to quit.")

        while True:
            question = input("\nYou: ").strip()
            if not question:
                continue
            if question.lower() in {"exit", "quit"}:
                print("Bye.")
                break

            try:
                query_embedding = embed_text(base_url, embed_model, question)
                retrieved = retrieve_context(query_embedding, records, top_k=top_k)

                if not retrieved:
                    print(
                        "Assistant: I do not have enough information in the provided context."
                    )
                    continue

                best_score = float(retrieved[0]["score"])
                if best_score < min_similarity:
                    print(
                        "Assistant: I do not have enough information in the provided context."
                    )
                    print(
                        f"Top similarity: {best_score:.4f} (below {min_similarity:.4f})"
                    )
                    continue

                answer = generate_answer(
                    base_url,
                    chat_model,
                    question,
                    retrieved,
                    max_context_chars=max_context_chars,
                    request_timeout=request_timeout,
                )
                print(f"Assistant: {answer}")

                sources = ", ".join(str(row["chunk_id"]) for row in retrieved)
                print(f"Sources: {sources}")
                print(f"Top similarity: {best_score:.4f}")
            except requests.Timeout:
                logger.error("Chat request timed out.", exc_info=True)
                print(
                    "Assistant: Request timed out. Try again or increase CHAT_REQUEST_TIMEOUT."
                )
            except requests.RequestException:
                logger.error("Network/API error while calling Ollama.", exc_info=True)
                print("Assistant: Ollama request failed. Check Ollama is running.")
            except Exception:
                logger.error("Unexpected error while answering.", exc_info=True)
                print(
                    "Assistant: An unexpected error occurred. Check logs/errorlogs.txt."
                )
    except Exception as exc:
        logger.error("Chatbot failed: %s", exc, exc_info=True)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
