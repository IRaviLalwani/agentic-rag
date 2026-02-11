# Product Notes

## Product Goal

Agentic-RAG is a local, Ollama-based RAG product that:

1. acquires knowledge from Wikipedia
2. transforms it into retrievable vectors
3. serves grounded answers through a chatbot

## Runtime Lifecycle

1. `scrape`: `src/scraper/scraper.py`
2. `pipeline`: `src/pipeline/main.py`
3. `chatbot`: `src/chatbot/chatbot.py`

## Storage Contracts

- Raw text: `scraped_pages/*.txt`
- Chunks: `artifacts/chunks/chunks.jsonl`
- Embeddings: `artifacts/embeddings/embeddings.jsonl`
- Ingested DB: `artifacts/ingest/rag.sqlite3` (`chunks` table)
- Error logs: `logs/errorlogs.txt`

## Entrypoint

- Product CLI: `main.py`
  - `uv run main.py scrape`
  - `uv run main.py pipeline`
  - `uv run main.py chatbot`
  - `uv run main.py build`
