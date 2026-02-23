# Alta Facil Pro

Alta Facil Pro is a multi-page Streamlit app for Spanish autonomos. It turns invoices into structured ledger entries via OCR + AI extraction, then applies deterministic IVA/IRPF rules to show real-time tax projections.

It includes a scanner workflow, dashboard KPIs, FP&A projections, and an AI tax assistant grounded in your own ledger data.

## RAG System (El Gestor chatbot)

The chatbot uses a **Retrieval-Augmented Generation (RAG)** pipeline so answers are grounded in your actual financial data rather than generic knowledge:

- **Vector store:** ChromaDB, persisted locally to `data/chroma/`
- **Embeddings:** OpenAI `text-embedding-3-small`
- **Two collections:**
  - `ledger_entries` — one document per ledger row, serialised to natural language and upserted by UUID
  - `tax_rules` — one document per rule category from `data/tax_rules_2025.json`, with fixed deterministic IDs (idempotent)
- **Index sync:**
  - Full re-index on chatbot page load (`index_ledger()` + `index_tax_rules()`)
  - Single-entry upsert after each invoice save (`index_entry()`)
- **Retrieval:** on every user message, `retrieve_context()` fetches the top-5 most relevant ledger entries and top-3 most relevant tax rules via cosine similarity, then injects them into the Claude system prompt
- **Graceful degradation:** if ChromaDB or the OpenAI key is unavailable, the chatbot falls back to aggregate-summary mode without crashing

Requires `OPENAI_API_KEY` in your `.env` to activate RAG. Without it the chatbot still works using the quarterly summary injected directly into the system prompt.

## Screenshot

![Screenshot placeholder](docs/screenshot-placeholder.png)

## Setup (condensed)

1. System deps (macOS):
```bash
brew install tesseract tesseract-lang poppler
```

2. Python deps:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Env vars:
```bash
cp .env.example .env
# set ANTHROPIC_API_KEY (and optional Gmail/Calendly vars)
```

## Run

```bash
streamlit run app.py
```

## Architecture

See `ARCHITECTURE (1).md` for the full system design, data flow, and engine/page responsibilities.

## Assignment

PDAI Assignment 1, ESADE.
