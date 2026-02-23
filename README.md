# Alta Facil Pro

Alta Facil Pro is a multi-page Streamlit app for Spanish autonomos. It turns invoices into structured ledger entries via OCR + AI extraction, then applies deterministic IVA/IRPF rules to show real-time tax projections.

It includes a scanner workflow, dashboard KPIs, FP&A projections, and an AI tax assistant grounded in your own ledger data.

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
