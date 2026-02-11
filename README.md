# Agentic-RAG Product

End-to-end local RAG product with three stages:

1. `scraper`: fetch topic content from Wikipedia into text files
2. `pipeline`: chunk -> embedding -> ingest into SQLite
3. `chatbot`: answer user questions from ingested context only

## Project Structure

```text
Agentic-RAG/
|-- main.py
|-- .env
|-- .env.example
|-- src/
|   |-- scraper/
|   |   `-- scraper.py
|   |-- pipeline/
|   |   |-- logger.py
|   |   |-- chunk.py
|   |   |-- embedding.py
|   |   |-- ingest.py
|   |   `-- main.py
|   `-- chatbot/
|       `-- chatbot.py
|-- scraped_pages/
|-- artifacts/
|   |-- chunks/
|   |-- embeddings/
|   `-- ingest/
`-- logs/
    `-- errorlogs.txt
```

## Quick Start

```bash
uv sync
```

Copy `.env.example` into `.env` and edit values as needed.

### One command per stage

```bash
uv run main.py scrape
uv run main.py pipeline
uv run main.py chatbot
```

### Build knowledge base in one step (scrape + pipeline)

```bash
uv run main.py build
```

If you run `uv run main.py` with no command, it defaults to `scrape`.

## Environment Variables

### Scraper

```env
WIKI_SUBJECT=AI
WIKI_ALLOW_INSECURE=false
WIKI_MAX_WORKERS=4
```

- `WIKI_SUBJECT` supports comma-separated values, e.g. `AI,Machine learning,Computer vision`.
- `WIKI_MAX_WORKERS` controls parallel scraping workers.

### Pipeline

```env
CHUNK_SIZE=1200
CHUNK_OVERLAP=200
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_EMBED_MODEL=
```

- File and folder paths are centralized in `src/path_config.py`.

### Chatbot

```env
OLLAMA_CHAT_MODEL=llama3.2:3b
CHAT_TOP_K=4
CHAT_MIN_SIMILARITY=0.15
CHAT_MAX_CONTEXT_CHARS=3600
CHAT_REQUEST_TIMEOUT=300
```

## Data Flow

1. `src/scraper/scraper.py` writes one or more files to the configured scraped output directory.
2. `src/pipeline/chunk.py` reads one or more scraped files and writes `artifacts/chunks/chunks.jsonl`
3. `src/pipeline/embedding.py` writes `artifacts/embeddings/embeddings.jsonl`
4. `src/pipeline/ingest.py` refreshes and writes `artifacts/ingest/rag.sqlite3`
5. `src/chatbot/chatbot.py` retrieves from SQLite + asks Ollama chat model

## Logging and Errors

- Pipeline and chatbot logs write errors to `logs/errorlogs.txt`
- Pipeline stage progress is printed to console (start/progress/completed)

## Product Docs

- `docs/PRODUCT.md`
