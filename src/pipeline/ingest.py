from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from logger import get_logger

from path_config import get_embedding_output_file, get_ingest_db_path


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"Embedding file not found: {path}. Run embedding.py first."
        )

    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def run() -> Path:
    logger = get_logger("pipeline.ingest")
    logger.info("Ingest process is starting.")

    load_dotenv()

    embedding_file = get_embedding_output_file()
    db_path = get_ingest_db_path()

    rows = read_jsonl(embedding_file)
    logger.info("Ingest process is going on for %d records.", len(rows))

    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                chunk_index INTEGER NOT NULL,
                source_file TEXT NOT NULL,
                text TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                embedding_dim INTEGER NOT NULL,
                model TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Keep DB in sync with the latest embedding file instead of accumulating stale rows.
        connection.execute("DELETE FROM chunks")

        connection.executemany(
            """
            INSERT OR REPLACE INTO chunks (
                chunk_id,
                chunk_index,
                source_file,
                text,
                embedding_json,
                embedding_dim,
                model
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["chunk_id"],
                    int(row["chunk_index"]),
                    row["source_file"],
                    row["text"],
                    json.dumps(row["embedding"]),
                    int(row["embedding_dim"]),
                    row["model"],
                )
                for row in rows
            ],
        )

        connection.commit()

        total = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    finally:
        connection.close()

    logger.info("Ingest completed. Ingested records this run: %d", len(rows))
    logger.info("Total rows currently in DB: %d", total)
    logger.info("SQLite DB location: %s", db_path)
    return db_path


def main() -> None:
    logger = get_logger("pipeline.ingest")
    try:
        run()
    except Exception as exc:
        logger.error("Ingest failed: %s", exc, exc_info=True)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
