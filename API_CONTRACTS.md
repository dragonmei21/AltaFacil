# API_CONTRACTS.md — Alta Fácil Pro

> **What this document is:** The exact input and output contracts for every engine function and external API call. Use this as the reference when calling a function or implementing it. If the function returns something different from what's here, that's a bug.

---

## 1. Internal Engine Contracts

### 1.1 `engine/invoice_parser.py`

#### `preprocess_image(img)`
```
INPUT:
  img: np.ndarray   # RGB or BGR image loaded from PIL/cv2

OUTPUT:
  np.ndarray        # Binary (0 or 255) grayscale image, same dimensions as input

SIDE EFFECTS: None
RAISES: Nothing (pure transformation)
```

#### `extract_text_from_image(file_bytes)`
```
INPUT:
  file_bytes: bytes   # Raw bytes of JPG, PNG, or HEIC file

OUTPUT:
  str   # Raw OCR text. May contain noise, line breaks, special chars.
        # Minimum viable output: 20 chars (below this → caller raises ValueError)

SIDE EFFECTS: None
RAISES:
  ValueError  if pytesseract not installed or tesseract binary not found
```

#### `extract_text_from_pdf(file_bytes)`
```
INPUT:
  file_bytes: bytes   # Raw bytes of PDF file

OUTPUT:
  str   # Extracted text from all pages, joined with "\n\n"
        # May be empty string if scanned PDF with no text layer (fallback to OCR)

SIDE EFFECTS: None
RAISES:
  ValueError  if PDF is encrypted/password-protected
```

#### `parse_with_claude(raw_text, client)`
```
INPUT:
  raw_text: str               # OCR or PDF-extracted text (any length)
  client: anthropic.Anthropic  # Initialized Anthropic client

OUTPUT (success):
  {
    "proveedor": str,             # Vendor name. Never null. Default "Desconocido" if not found.
    "nif_proveedor": str | None,  # Tax ID. Null if not present.
    "fecha": str,                 # "YYYY-MM-DD". Default today's date if not found.
    "numero_factura": str | None, # Invoice number. Null if not present.
    "base_imponible": float,      # Pre-tax amount. Always positive. Default 0.0.
    "tipo_iva": int,              # 0, 4, 10, or 21. Default 21.
    "cuota_iva": float,           # VAT amount. Recalculated by caller if suspicious.
    "total": float,               # Total amount including VAT.
    "concepto": str,              # Short description. Never null.
    "tipo_documento": str         # "factura" | "ticket" | "recibo" | "otro"
  }

OUTPUT (parse error):
  {
    "error": str,        # json.JSONDecodeError message
    "raw": str,          # Claude's raw response text (for debugging)
    "parse_error": True
  }

SIDE EFFECTS: Makes Anthropic API call (model: claude-haiku-4-5, max_tokens: 500, temperature: 0)
RAISES:
  anthropic.APIError   if API key invalid or rate limit hit
```

#### `process_document(file_bytes, file_type, user_profile, tax_rules, claude_client)`
```
INPUT:
  file_bytes: bytes                # Raw file content
  file_type: str                   # "pdf" | "image"
  user_profile: dict               # From data/user_profile.json (see Section 2.1)
  tax_rules: dict                  # From load_tax_rules() (see Section 2.3)
  claude_client: anthropic.Anthropic

OUTPUT:
  {
    # --- From Claude extraction ---
    "proveedor": str,
    "nif_proveedor": str | None,
    "fecha": str,                     # "YYYY-MM-DD"
    "numero_factura": str | None,
    "base_imponible": float,
    "tipo_iva": int,                  # Always recalculated if discrepancy > €0.05
    "cuota_iva": float,               # Always = base_imponible × tipo_iva / 100
    "total": float,
    "concepto": str,
    "tipo_documento": str,

    # --- From classify_iva() ---
    "iva_label": str,                 # e.g. "Tipo general"
    "iva_article": str,               # e.g. "Art. 90.Uno Ley 37/1992"
    "iva_confidence": str,            # "high" | "low"
    "exempt": bool,

    # --- From classify_deductibility() ---
    "deducible": bool,
    "porcentaje_deduccion": int,      # 0 | 30 | 50 | 100
    "cuota_iva_deducible": float,     # cuota_iva × porcentaje_deduccion / 100
    "deductibility_justification": str,  # Human-readable, translated via t()
    "deductibility_article": str,    # Spanish legal citation, never translated

    # --- Pipeline metadata ---
    "extraction_method": str,        # "pdfplumber" | "tesseract" | "claude_only"
    "parse_error": bool,             # True only if Claude returned malformed JSON
    "iva_discrepancy": bool          # True if extracted cuota differed > €0.05
  }

RAISES:
  ValueError  if OCR text < 20 chars ("OCR failed — image quality too low")
  anthropic.APIError  if Claude API unavailable
```

---

### 1.2 `engine/tax_rules.py`

#### `load_tax_rules()`
```
INPUT: None (reads data/tax_rules_2025.json)

OUTPUT:
  {
    "version": str,
    "source": str,
    "iva_rates": {
      "21": {"label": str, "article": str, "keywords": list[str]},
      "10": {"label": str, "article": str, "keywords": list[str]},
      "4":  {"label": str, "article": str, "keywords": list[str]},
      "0":  {"label": str, "article": str, "keywords": list[str]}
    },
    "deductibility_rules": {
      "full_100":     {"article": str, "keywords": list[str]},
      "partial_50":   {"article": str, "keywords": list[str], "pct": 50},
      "partial_home": {"article": str, "keywords": list[str], "pct": 30, "condition": str},
      "zero_0":       {"article": str, "keywords": list[str], "pct": 0}
    }
  }

RAISES:
  FileNotFoundError  if data/tax_rules_2025.json missing
```

#### `classify_iva(concepto, proveedor, rules, lang)`
```
INPUT:
  concepto: str    # Service/product description from invoice
  proveedor: str   # Vendor name from invoice
  rules: dict      # Output of load_tax_rules()
  lang: str        # "es" | "en" — for translated label

OUTPUT:
  {
    "tipo_iva": int,          # 0 | 4 | 10 | 21
    "label": str,             # Translated rate name via t()
    "article": str,           # Spanish legal citation (never translated)
    "exempt": bool,           # True only for Art. 20 exempt operations
    "confidence": str,        # "high" (keyword match) | "low" (default fallback)
    "match_keyword": str      # The exact keyword that triggered the match. "" if default.
  }

RAISES: Nothing (always returns a valid dict — defaults to 21% if no match)
```

#### `classify_deductibility(concepto, tipo_iva, exempt, user_profile, rules, lang)`
```
INPUT:
  concepto: str       # Service/product description
  tipo_iva: int       # 0 | 4 | 10 | 21
  exempt: bool        # True if Art. 20 exempt
  user_profile: dict  # Must contain "work_location" key
  rules: dict         # Output of load_tax_rules()
  lang: str           # "es" | "en"

OUTPUT:
  {
    "deducible": bool,
    "porcentaje_deduccion": int,      # 0 | 30 | 50 | 100
    "cuota_iva_deducible": float,     # Pass cuota_iva to get this, but function
                                      # returns the PERCENTAGE only — caller multiplies
    "justification": str,             # Translated explanation via t("tax_verdicts.X")
    "article": str                    # Spanish legal citation
  }

NOTE: cuota_iva_deducible in this output = 0.0 placeholder.
      Caller computes: cuota_iva × porcentaje_deduccion / 100
      (This keeps the function pure — no money amounts needed here)

RAISES: Nothing (always returns valid dict)
```

#### `calculate_modelo_303(df_quarter)`
```
INPUT:
  df_quarter: pd.DataFrame  # Ledger rows for one quarter only (pre-filtered)
                             # Must have columns: tipo, cuota_iva, cuota_iva_deducible

OUTPUT:
  {
    "iva_cobrado": float,              # Sum cuota_iva WHERE tipo="ingreso"
    "iva_soportado_total": float,      # Sum cuota_iva WHERE tipo="gasto"
    "iva_soportado_deducible": float,  # Sum cuota_iva_deducible WHERE tipo="gasto"
    "resultado": float,                # iva_cobrado - iva_soportado_deducible
    "a_pagar": float,                  # max(0, resultado)
    "a_compensar": float               # abs(min(0, resultado))
  }

RAISES: Nothing (returns zeros if DataFrame empty)
```

#### `calculate_modelo_130(df_ytd, retenciones_ytd)`
```
INPUT:
  df_ytd: pd.DataFrame    # All ledger entries from start of year to end of current quarter
  retenciones_ytd: float  # Sum of IRPF withholdings already received from clients

OUTPUT:
  {
    "ingresos_ytd": float,
    "gastos_deducibles_ytd": float,
    "beneficio_ytd": float,
    "pago_fraccionado_bruto": float,   # beneficio_ytd × 0.20
    "retenciones_ytd": float,
    "pago_neto": float                 # max(0, bruto - retenciones)
  }

RAISES: Nothing
```

#### `get_cuota_ss(net_monthly_income, tarifa_plana, tarifa_plana_active)`
```
INPUT:
  net_monthly_income: float  # Estimated monthly net income (€)
  tarifa_plana: bool         # User applied for tarifa plana
  tarifa_plana_active: bool  # Tarifa plana period still valid

OUTPUT:
  float   # Monthly SS cuota in EUR
          # Returns 80.0 if tarifa_plana AND tarifa_plana_active
          # Otherwise: bracket lookup from SS_BRACKETS

RAISES: Nothing
```

---

### 1.3 `engine/finance_engine.py`

#### `load_ledger()`
```
INPUT: None (reads data/ledger.csv)

OUTPUT:
  pd.DataFrame with columns: [see CLAUDE.md Section 3.1]
  Dtypes enforced:
    base_imponible, cuota_iva, total, cuota_iva_deducible → float64
    tipo_iva, porcentaje_deduccion → int64
    deducible → bool
    fecha, id, tipo, proveedor_cliente, ... → object (str)

  If file does not exist: returns empty DataFrame with correct columns and dtypes

RAISES:
  pd.errors.ParserError  if CSV is corrupted (bubble up to UI)
```

#### `save_to_ledger(entry)`
```
INPUT:
  entry: dict  # Keys matching LEDGER_COLUMNS. Missing keys filled with defaults:
               # id → uuid4 string
               # trimestre → derived from entry["fecha"] via get_current_quarter()
               # estado → "pendiente"
               # origen → "manual" if not provided

OUTPUT:
  str   # The UUID id that was assigned to the new entry

SIDE EFFECTS:
  1. Appends one row to data/ledger.csv
  2. Calls get_cached_ledger.clear() to invalidate Streamlit cache

RAISES:
  ValueError   if entry["fecha"] is not parseable as YYYY-MM-DD
  IOError      if data/ledger.csv cannot be written (permissions issue)
```

#### `get_current_quarter(d)`
```
INPUT:
  d: date | None   # date object. Uses today if None.

OUTPUT:
  str   # Format: "YYYY-QN"
        # Examples: date(2025,1,15) → "2025-Q1"
        #           date(2025,4,1)  → "2025-Q2"
        #           date(2025,7,31) → "2025-Q3"
        #           date(2025,10,1) → "2025-Q4"

RAISES: Nothing
```

#### `get_quarterly_summary(df, quarter)`
```
INPUT:
  df: pd.DataFrame  # Full ledger (all rows)
  quarter: str      # "YYYY-QN" format

OUTPUT:
  {
    "total_ingresos": float,
    "total_gastos_base": float,
    "total_gastos_deducibles": float,
    "iva_cobrado": float,
    "iva_soportado_deducible": float,
    "resultado_303": float,
    "beneficio_neto": float,
    "irpf_provision": float,
    "n_facturas": int,
    "n_gastos": int
  }
  NOTE: All float fields return 0.0 if no data for the quarter. Never NaN.

RAISES: Nothing
```

#### `get_monthly_breakdown(df, year)`
```
INPUT:
  df: pd.DataFrame  # Full ledger
  year: int         # 4-digit year, e.g. 2025

OUTPUT:
  pd.DataFrame with columns:
    month: int (1–12)
    ingresos: float
    gastos_base: float
    tax_provision: float   # (ingresos - gastos_base) × 0.20, floor at 0
  
  All 12 months present, even if no data (filled with 0.0)

RAISES: Nothing
```

#### `get_ar_aging(df)`
```
INPUT:
  df: pd.DataFrame  # Full ledger

OUTPUT:
  pd.DataFrame  # Only ingreso rows where estado != "pagado"
                # Sorted by fecha ASC (oldest first)
                # Extra columns added:
                #   days_outstanding: int (today - fecha)
                #   aging_bucket: str ("0-30" | "31-60" | "61-90" | "90+")

RAISES: Nothing (returns empty DataFrame if no outstanding AR)
```

---

### 1.4 `engine/gmail_watcher.py`

#### `check_new_invoices(credentials_path, last_check_timestamp, user_profile, tax_rules, claude_client)`
```
INPUT:
  credentials_path: str       # Path to Google OAuth credentials.json
  last_check_timestamp: str   # ISO datetime string, e.g. "2025-04-01T10:30:00"
  user_profile: dict
  tax_rules: dict
  claude_client: anthropic.Anthropic

OUTPUT:
  list[dict]   # List of process_document() output dicts (see Section 1.1)
               # Each dict has extra keys: "origen": "gmail",
               #   "email_subject": str, "email_date": str
               # Returns [] if no new invoices found or auth fails

SIDE EFFECTS: None (caller decides whether to save to ledger)
RAISES: Nothing (all errors caught internally, logged, return [])
```

#### `get_mock_invoices()`
```
INPUT: None

OUTPUT:
  list[dict]   # 3 hardcoded process_document()-format dicts representing
               # realistic Spanish invoices (for demo mode)

RAISES: Nothing
```

---

### 1.5 `engine/calendly_client.py`

#### `get_user_uri(token)`
```
INPUT:
  token: str   # Calendly Personal Access Token

OUTPUT:
  str   # User URI, e.g. "https://api.calendly.com/users/ABCD1234"

RAISES:
  requests.HTTPError   if token invalid (401)
```

#### `get_scheduled_events(token, user_uri, min_start_time)`
```
INPUT:
  token: str
  user_uri: str
  min_start_time: str | None   # ISO datetime, filters events after this time

OUTPUT:
  list[dict] where each dict:
  {
    "event_uuid": str,
    "nombre_evento": str,
    "cliente_nombre": str,
    "cliente_email": str,
    "fecha_inicio": str,      # ISO datetime
    "fecha_fin": str,
    "estado": str,            # "activo" | "completado" | "cancelado"
    "precio": float | None
  }

RAISES:
  requests.HTTPError   on API errors
```

#### `generate_invoice_draft(event, user_profile)`
```
INPUT:
  event: dict          # Normalized event dict from get_scheduled_events()
  user_profile: dict

OUTPUT:
  dict   # Ledger-schema dict with these fields pre-filled:
  {
    "tipo": "ingreso",
    "proveedor_cliente": event["cliente_nombre"],
    "concepto": event["nombre_evento"],
    "fecha": event["fecha_inicio"][:10],       # date part only
    "tipo_iva": 21,                            # Default for professional services
    "base_imponible": event["precio"] or 0.0,  # 0 if Calendly doesn't provide price
    "cuota_iva": base × 0.21,
    "total": base + cuota,
    "estado": "pendiente",
    "origen": "calendly",
    "numero_factura": None                      # User fills in
  }

RAISES: Nothing
```

---

### 1.6 `i18n/__init__.py`

#### `t(key, **kwargs)`
```
INPUT:
  key: str        # Dot-notation string key, e.g. "scanner.btn_analyze"
  **kwargs: any   # Format substitutions, e.g. name="María", amount=450.0

OUTPUT:
  str   # Translated string in current language (from st.session_state["lang"])
        # Falls back to Spanish if key missing in English
        # Returns key itself if missing in both (never crashes)

RAISES: Nothing
```

#### `tax_term(key)`
```
INPUT:
  key: str   # Tax term key without prefix, e.g. "modelo_303"

OUTPUT:
  tuple[str, str | None]   # (label, tooltip)
  # label: always the Spanish term (same in both languages)
  # tooltip: English explanation string | None if empty in current language

RAISES: Nothing
```

#### `tax_header(key)`
```
INPUT:
  key: str   # Tax term key, e.g. "modelo_303"

OUTPUT: None (renders directly to Streamlit)
  # Calls: st.subheader(label)
  # If tooltip non-empty: st.caption(f"ℹ️ {tooltip}")

SIDE EFFECTS: Renders 1-2 Streamlit widgets
RAISES: Nothing
```

---

## 2. Data File Schemas (Reference)

### 2.1 `data/user_profile.json`
```json
{
  "nombre": "string — required",
  "actividad": "string — required",
  "iae_code": "string | null",
  "iva_regime": "general | simplificado | exento",
  "irpf_retencion_pct": 0 | 7 | 15 | 19,
  "work_location": "casa | oficina | mixto",
  "home_office_pct": 5..50,
  "ss_bracket_monthly": 200..1267,
  "tarifa_plana": true | false,
  "tarifa_plana_end_date": "YYYY-MM-DD | null",
  "alta_date": "YYYY-MM-DD",
  "autonomia": "peninsular | canarias | ceuta_melilla",
  "onboarding_complete": true | false
}
```

### 2.2 Single Ledger Row
```json
{
  "id": "uuid4-string",
  "fecha": "YYYY-MM-DD",
  "tipo": "gasto | ingreso",
  "proveedor_cliente": "string",
  "nif": "string | null",
  "concepto": "string",
  "numero_factura": "string | null",
  "base_imponible": 0.0,
  "tipo_iva": 0 | 4 | 10 | 21,
  "cuota_iva": 0.0,
  "total": 0.0,
  "deducible": true | false,
  "porcentaje_deduccion": 0 | 30 | 50 | 100,
  "cuota_iva_deducible": 0.0,
  "aeat_articulo": "string",
  "trimestre": "YYYY-QN",
  "estado": "pendiente | pagado | vencido",
  "origen": "scanner | gmail | calendly | manual"
}
```

### 2.3 `data/tax_rules_2025.json` (abbreviated)
```json
{
  "version": "2025-07-31",
  "source": "AEAT Ley 37/1992",
  "iva_rates": { "21": {...}, "10": {...}, "4": {...}, "0": {...} },
  "deductibility_rules": { "full_100": {...}, "partial_50": {...}, ... }
}
```

---

## 3. External API Contracts

### 3.1 Anthropic Claude API

#### Invoice Extraction Call
```
POST https://api.anthropic.com/v1/messages
Headers:
  x-api-key: {ANTHROPIC_API_KEY}
  anthropic-version: 2023-06-01

Body:
{
  "model": "claude-haiku-4-5",
  "max_tokens": 500,
  "temperature": 0,
  "system": "Eres un experto en facturas españolas. Extrae los campos solicitados con precisión. Devuelve SOLO JSON válido, sin texto adicional, sin backticks, sin explicaciones.",
  "messages": [
    {"role": "user", "content": "Del siguiente texto...\n{raw_text}"}
  ]
}

EXPECTED RESPONSE content[0].text:
  Valid JSON string matching parse_with_claude() output schema (Section 1.1)
  If Claude returns markdown code fences: strip ```json ... ``` before parsing
```

#### Chatbot Call
```
POST https://api.anthropic.com/v1/messages

Body:
{
  "model": "claude-sonnet-4-6",
  "max_tokens": 1000,
  "system": "{dynamic system prompt with user profile + quarterly summary}",
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."},
    {"role": "user", "content": "{current prompt}"}
  ]
}

EXPECTED RESPONSE content[0].text:
  Natural language response in active language (ES or EN)
  Ends with disclaimer: "Para declaraciones oficiales, consulta siempre con tu gestor"
```

### 3.2 Calendly REST API v2

```
Base URL: https://api.calendly.com
Auth header: Authorization: Bearer {CALENDLY_ACCESS_TOKEN}

GET /users/me
  Response: { "resource": { "uri": "https://api.calendly.com/users/XXXX", ... } }

GET /scheduled_events?user={user_uri}&status=active,completed&min_start_time={ISO}
  Response: {
    "collection": [
      {
        "uri": "https://api.calendly.com/scheduled_events/UUID",
        "name": "string",
        "status": "active | canceled | completed",
        "start_time": "ISO datetime",
        "end_time": "ISO datetime",
        "event_type": "https://api.calendly.com/event_types/UUID"
      }
    ]
  }

GET /scheduled_events/{uuid}/invitees
  Response: {
    "collection": [
      { "name": "string", "email": "string@example.com" }
    ]
  }
```

### 3.3 Gmail API (via simplegmail)

```python
# Internal interface — not a direct HTTP call
from simplegmail import Gmail

gmail = Gmail()  # Uses credentials.json for OAuth

messages = gmail.get_messages(query=f"after:{timestamp} has:attachment")
for msg in messages:
    for attachment in msg.attachments:
        # attachment.filename: str
        # attachment.data: bytes (base64-decoded content)
        # attachment.content_type: str (e.g. "application/pdf")
```

---

## 4. Interface Drift Prevention

If you change any function signature or return schema in this document, you MUST:
1. Update this file (`API_CONTRACTS.md`)
2. Update `CLAUDE.md` Section 5 (function signatures)
3. Update `DATA_FLOW.md` if the data path changes
4. Update any unit tests in `tests/`
5. Search codebase for all call sites of the changed function and update them

**Never change a function's return schema silently.** If a page expects `result["iva_label"]` and the engine starts returning `result["label"]`, the page will crash with a `KeyError` that is hard to trace. Schema changes must be coordinated across all layers.
