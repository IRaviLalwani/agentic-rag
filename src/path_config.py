from __future__ import annotations

from pathlib import Path

DEFAULT_SCRAPED_OUTPUT_DIR = Path("scraped_pages")
DEFAULT_CHUNK_OUTPUT_FILE = Path("artifacts/chunks/chunks.jsonl")
DEFAULT_EMBEDDING_OUTPUT_FILE = Path("artifacts/embeddings/embeddings.jsonl")
DEFAULT_INGEST_DB_PATH = Path("artifacts/ingest/rag.sqlite3")
DEFAULT_LOG_DIR = Path("logs")
DEFAULT_ERROR_LOG_FILE = DEFAULT_LOG_DIR / "errorlogs.txt"


def get_scraped_output_dir() -> Path:
    return DEFAULT_SCRAPED_OUTPUT_DIR


def get_chunk_output_file() -> Path:
    return DEFAULT_CHUNK_OUTPUT_FILE


def get_embedding_output_file() -> Path:
    return DEFAULT_EMBEDDING_OUTPUT_FILE


def get_ingest_db_path() -> Path:
    return DEFAULT_INGEST_DB_PATH


def get_log_dir() -> Path:
    return DEFAULT_LOG_DIR


def get_error_log_file() -> Path:
    return DEFAULT_ERROR_LOG_FILE
