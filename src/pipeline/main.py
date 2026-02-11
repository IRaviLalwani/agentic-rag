from __future__ import annotations

import chunk
import embedding
import ingest
from logger import get_logger


def main() -> None:
    logger = get_logger("pipeline.main")

    try:
        logger.info("Pipeline started: chunk -> embedding -> ingest")

        chunk_output = chunk.run()
        logger.info("Chunk step finished: %s", chunk_output)

        embedding_output = embedding.run()
        logger.info("Embedding step finished: %s", embedding_output)

        db_path = ingest.run()
        logger.info("Ingest step finished: %s", db_path)

        logger.info("Pipeline completed successfully.")
    except Exception as exc:
        logger.error("Pipeline failed: %s", exc, exc_info=True)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
