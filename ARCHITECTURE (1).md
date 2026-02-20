# ARCHITECTURE.md — Alta Fácil Pro

> **What this document is:** How the system is built. Modules, responsibilities, dependency rules, and data flow at a structural level. Read this before touching any code.

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER (Browser)                           │
└─────────────────────────┬───────────────────────────────────────┘
                          │  HTTP (localhost:8501)
┌─────────────────────────▼───────────────────────────────────────┐
│                   STREAMLIT UI LAYER                            │
│   app.py  │  pages/0-5  │  shared sidebar  │  i18n/            │
│   (routing, session init, lang switcher)                        │
└──────┬────────────┬──────────────┬──────────────────────────────┘
       │            │              │
       ▼            ▼              ▼
┌──────────┐ ┌──────────┐ ┌───────────────┐
│  engine/ │ │  engine/ │ │    engine/    │
│ finance  │ │  tax_    │ │   invoice_    │
│ _engine  │ │  rules   │ │   parser      │
└──────┬───┘ └─────┬────┘ └───────┬───────┘
       │           │              │
       ▼           ▼              ▼
┌──────────────────────────────────────────┐
│              DATA LAYER                  │
│  data/ledger.csv  │  data/user_profile   │
│  data/tax_rules_2025.json                │
└──────────────────────────────────────────┘
       │                          │
       ▼                          ▼
┌─────────────┐          ┌─────────────────┐
│  engine/    │          │  External APIs  │
│  gmail_     │          │  Anthropic API  │
│  watcher    │          │  (Claude)       │
│  calendly_  │          │                 │
│  client     │          └─────────────────┘
└─────────────┘
```

**Key principle:** Data flows in one direction. Pages call engine functions. Engine functions read/write data. Pages never write data directly.

---

## 2. Layer Responsibilities

### Layer 1 — Streamlit UI (`app.py`, `pages/`)
- Renders widgets
- Reads from `st.session_state`
- Calls engine functions — never implements business logic itself
- Handles user events (button clicks, form submits)
- Calls `t()` for all user-facing strings
- **Never** writes directly to `data/` — always calls engine functions

### Layer 2 — Engine (`engine/`)
- Pure Python — no Streamlit imports except where explicitly noted
- Implements all business logic: OCR, tax classification, financial calculations
- Reads/writes `data/` files
- Calls external APIs (Anthropic, Gmail, Calendly)
- Returns plain Python dicts, DataFrames, or primitives — never Streamlit widgets

### Layer 3 — i18n (`i18n/`)
- Manages all user-facing strings
- Provides `t(key)`, `tax_term(key)`, `tax_header(key)` helpers
- Reads JSON files — no business logic, no Streamlit state
- Can be imported by both UI layer and engine layer (for translated justifications)

### Layer 4 — Data (`data/`)
- Flat files only: CSV and JSON
- Never imported directly by pages — always via engine functions
- `ledger.csv` is append-only at runtime (never rewritten wholesale)
- `tax_rules_2025.json` is read-only at runtime

---

## 3. Module Map

```
altafacil_pro/
│
├── app.py
│   Responsibility: Entry point. Session state init. Route to onboarding if first run.
│   Imports: streamlit, pathlib, json, i18n
│   Does NOT import: any engine module directly
│
├── pages/
│   ├── 0_Onboarding.py
│   │   Responsibility: First-run quiz. Saves user_profile.json.
│   │   Imports: streamlit, i18n, engine.finance_engine (for save path)
│   │
│   ├── 1_Dashboard.py
│   │   Responsibility: KPI cards, cashflow chart, recent transactions, Gmail toast.
│   │   Imports: streamlit, plotly, i18n, engine.finance_engine, engine.gmail_watcher
│   │
│   ├── 2_Scanner.py
│   │   Responsibility: Upload/camera/manual invoice entry. AI extraction. Save to ledger.
│   │   Imports: streamlit, i18n, engine.invoice_parser, engine.finance_engine
│   │
│   ├── 3_AR_Agenda.py
│   │   Responsibility: Calendly events, issued invoices, AR aging table.
│   │   Imports: streamlit, i18n, engine.finance_engine, engine.calendly_client
│   │
│   ├── 4_FPA.py
│   │   Responsibility: Modelo 303/130 projections, what-if sliders, deadline countdown.
│   │   Imports: streamlit, plotly, i18n, engine.finance_engine, engine.tax_rules
│   │
│   └── 5_Chatbot.py
│       Responsibility: El Gestor chatbot. Dynamic system prompt with live ledger data.
│       Imports: streamlit, anthropic, i18n, engine.finance_engine
│
├── engine/
│   ├── __init__.py          # Empty
│   │
│   ├── tax_rules.py
│   │   Responsibility: IVA rate classification. Deductibility classification.
│   │                   Tax formula calculations (303, 130, IRPF brackets, SS).
│   │   Imports: json, pathlib, unicodedata, i18n (for translated justifications)
│   │   Does NOT import: streamlit, pandas, anthropic
│   │
│   ├── invoice_parser.py
│   │   Responsibility: OCR preprocessing. Text extraction from PDF/image.
│   │                   Claude structured extraction. Orchestrates full pipeline.
│   │   Imports: cv2, numpy, pytesseract, pdfplumber, PIL, anthropic, json, engine.tax_rules
│   │   Does NOT import: streamlit, pandas
│   │
│   ├── finance_engine.py
│   │   Responsibility: Ledger CRUD. Quarterly/YTD summaries. AR aging. Monthly breakdown.
│   │   Imports: pandas, uuid, datetime, pathlib
│   │   Does NOT import: streamlit, anthropic, engine.tax_rules, engine.invoice_parser
│   │
│   ├── gmail_watcher.py
│   │   Responsibility: Gmail OAuth. Inbox polling. Attachment download. Demo mode.
│   │   Imports: simplegmail, engine.invoice_parser
│   │   Does NOT import: streamlit, pandas
│   │
│   └── calendly_client.py
│       Responsibility: Calendly REST API. Event normalization. Invoice draft generation.
│       Imports: requests
│       Does NOT import: streamlit, pandas, engine.*
│
├── i18n/
│   ├── __init__.py          # t(), get_lang(), set_lang(), tax_term(), tax_header(), LANGS
│   ├── es.json              # ~150 Spanish strings (canonical)
│   └── en.json              # ~150 English strings (full translation)
│
└── data/
    ├── ledger.csv           # Runtime — append only
    ├── user_profile.json    # Runtime — written once at onboarding, editable in settings
    └── tax_rules_2025.json  # Static — never modified at runtime
```

---

## 4. Dependency Rules

These rules prevent circular imports and keep the architecture clean. **Violations will cause import errors or subtle bugs.**

```
ALLOWED:
  pages/     → engine/*         ✅
  pages/     → i18n             ✅
  engine/*   → i18n             ✅ (for translated justifications only)
  engine/invoice_parser → engine/tax_rules  ✅
  engine/gmail_watcher  → engine/invoice_parser  ✅

FORBIDDEN:
  engine/*   → pages/*          ❌  (engine has no UI knowledge)
  engine/*   → streamlit        ❌  (engine is pure Python)
  engine/finance_engine → engine/tax_rules  ❌  (finance knows nothing about tax)
  engine/finance_engine → engine/invoice_parser  ❌
  engine/tax_rules → engine/invoice_parser  ❌
  engine/calendly_client → engine/*  ❌
  i18n       → engine/*         ❌  (i18n has no business logic)
  i18n       → streamlit        ❌  (i18n is pure Python — tested independently)
  pages/*    → pages/*          ❌  (use st.switch_page for navigation)
  data/      → anything         ❌  (data files are not modules)
```

**Visual dependency graph:**
```
pages
  └─→ engine/invoice_parser
        └─→ engine/tax_rules
              └─→ i18n
  └─→ engine/finance_engine
  └─→ engine/gmail_watcher
        └─→ engine/invoice_parser (see above)
  └─→ engine/calendly_client
  └─→ i18n

No cycles. No engine importing streamlit.
```

---

## 5. State Architecture

Three types of state — each with different lifetime:

| State Type | Storage | Lifetime | Example |
|---|---|---|---|
| **Session state** | `st.session_state` | Browser session | `lang`, `messages`, `processed_document` |
| **Cached data** | `@st.cache_data` | TTL-based (30s for ledger) | `load_ledger()`, `load_tax_rules()` |
| **Persistent data** | `data/*.csv` / `data/*.json` | Forever | Ledger entries, user profile |

Full session state spec: see `STATE_MANAGEMENT.md`.

---

## 6. AI Integration Points

Two distinct Claude integrations — different models, different purposes:

| Integration | Model | Location | Purpose | Temperature |
|---|---|---|---|---|
| **Invoice extraction** | `claude-haiku-4-5` | `engine/invoice_parser.py → parse_with_claude()` | Extract structured JSON from OCR text | `0` (deterministic) |
| **Chatbot** | `claude-sonnet-4-6` | `pages/5_Chatbot.py` | Answer tax questions with live context | default |

**Critical rule:** Claude NEVER classifies IVA rates or deductibility. That is always the deterministic rules engine in `engine/tax_rules.py`. Claude only extracts raw fields from invoice text.

---

## 7. Error Handling Architecture

```
UI Layer (pages/)
    │
    ├── try:
    │       result = engine_function(...)
    │   except ValueError as e:
    │       st.error(t("error.X", detail=str(e)))
    │       st.stop()
    │   except anthropic.APIError as e:
    │       st.error(t("common.error_api", error=str(e)))
    │       st.stop()
    │
Engine Layer (engine/)
    │
    ├── Raises ValueError for recoverable user errors
    │   (bad image quality, missing required field)
    │
    ├── Raises RuntimeError for unrecoverable system errors
    │   (file corruption, missing config)
    │
    └── NEVER silently returns None for error conditions
        ALWAYS either returns a valid result OR raises
```

Pages catch all engine exceptions. Engine never catches its own exceptions — it raises clearly.

---

## 8. Caching Strategy

```python
# ledger.csv — cache with 30s TTL, invalidate after every write
@st.cache_data(ttl=30)
def get_cached_ledger() -> pd.DataFrame:
    return load_ledger()

# After save_to_ledger():
get_cached_ledger.clear()

# tax_rules_2025.json — cache forever (static file)
@st.cache_data
def get_cached_tax_rules() -> dict:
    return load_tax_rules()

# Claude client — cache as resource (single instance per session)
@st.cache_resource
def get_claude_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# user_profile.json — loaded once into session state at app.py startup
# NOT cached via st.cache_data — lives in st.session_state["user_profile"]
```

---

## 9. File Naming Conventions

| Pattern | Convention | Example |
|---|---|---|
| Pages | `N_PascalCase.py` | `2_Scanner.py` |
| Engine modules | `snake_case.py` | `invoice_parser.py` |
| i18n files | `{lang_code}.json` | `es.json`, `en.json` |
| Data files | `snake_case.{ext}` | `ledger.csv`, `user_profile.json` |
| String keys | `section.subsection_action` | `"scanner.btn_analyze"` |
| Session state keys | `snake_case` strings | `"processed_document"` |
| Ledger columns | `snake_case` | `"base_imponible"`, `"tipo_iva"` |
