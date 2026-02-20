# DATA_FLOW.md — Alta Fácil Pro

> **What this document is:** Every path data takes through the system. Where it enters, how it transforms, where it's stored, where it exits. Read this when debugging unexpected values or adding new data paths.

---

## 1. Primary Flow — Invoice Scanning (AP Entry)

This is the core user journey. An expense invoice becomes a ledger entry.

```
INPUT: File (PDF / JPG / PNG / HEIC) or camera photo or manual form
         │
         ▼
[pages/2_Scanner.py]
  Read file bytes → determine file_type ("pdf" | "image")
         │
         ▼
[engine/invoice_parser.py → process_document()]
         │
         ├── IF image:
         │     extract_text_from_image(bytes)
         │       → preprocess_image(np.ndarray)
         │           → cv2 grayscale → denoise → Otsu threshold
         │       → pytesseract.image_to_string(lang='spa+eng')
         │       → raw_text: str
         │
         ├── IF pdf:
         │     extract_text_from_pdf(bytes)
         │       → try pdfplumber: extract text from all pages
         │       → if text < 50 chars: fallback to pdf2image → OCR each page
         │       → raw_text: str
         │
         ▼
[engine/invoice_parser.py → parse_with_claude()]
  raw_text → Claude claude-haiku-4-5 (temperature=0)
  System: "Eres experto en facturas españolas. Devuelve SOLO JSON."
  Returns JSON string → json.loads() → extracted_dict:
    {proveedor, nif_proveedor, fecha, numero_factura,
     base_imponible, tipo_iva, cuota_iva, total, concepto, tipo_documento}
         │
         ▼
[engine/invoice_parser.py — IVA consistency check]
  calculated_cuota = base_imponible × tipo_iva / 100
  if |extracted_cuota - calculated_cuota| > 0.05:
      flag discrepancy → use calculated_cuota
         │
         ▼
[engine/tax_rules.py → classify_iva()]
  input: concepto, proveedor, rules (from tax_rules_2025.json)
  process: normalize → keyword match (4% → 10% → exempt → 21%)
  output: {tipo_iva, label, article, exempt, confidence, match_keyword}
         │
         ▼
[engine/tax_rules.py → classify_deductibility()]
  input: concepto, tipo_iva, exempt, user_profile, rules
  process: keyword match (vehicle → home → non-deductible → professional → default)
           apply user_profile conditions (work_location for home office)
  output: {deducible, porcentaje_deduccion, cuota_iva_deducible, justification, article}
         │
         ▼
[process_document() assembles final result dict]
  Merges: extracted_dict + iva_classification + deductibility_classification + metadata
  Stored in: st.session_state["processed_document"]
         │
         ▼
[pages/2_Scanner.py — display to user]
  User sees: extracted fields + IVA verdict + deductibility verdict
  User can: edit any field → re-run classify_iva() + classify_deductibility()
  User clicks: "Save to ledger"
         │
         ▼
[engine/finance_engine.py → save_to_ledger()]
  Builds ledger entry dict (adds: id=UUID4, trimestre=derived, estado="pendiente")
  Appends row to data/ledger.csv
  Calls: get_cached_ledger.clear() → forces reload on next access

OUTPUT: New row in data/ledger.csv
        st.session_state["processed_document"] = None (cleared)
        st.balloons() + st.success() shown to user
```

---

## 2. Revenue Flow — AR Entry (from Calendly or Manual)

```
INPUT A (Calendly):
  GET https://api.calendly.com/scheduled_events
    → list of event dicts
    → normalize to internal format
    → display in pages/3_AR_Agenda.py
    → user clicks "Generate Invoice" on a completed event
    → engine/calendly_client.py → generate_invoice_draft(event, user_profile)
    → pre-filled draft dict → stored in st.session_state["invoice_draft"]
    → st.switch_page("pages/2_Scanner.py") with draft pre-loaded

INPUT B (Manual):
  User fills st.form() in pages/2_Scanner.py (method = "Enter manually")
  → manual_entry dict assembled from form fields
  → classify_iva() + classify_deductibility() run as normal

BOTH PATHS → save_to_ledger() → data/ledger.csv (tipo = "ingreso")
```

---

## 3. Automatic Gmail Flow (Phase 2, Demo Mode Available)

```
TRIGGER: st.session_state["last_gmail_check"] is None OR
         (now - last_gmail_check) > 15 minutes

[engine/gmail_watcher.py → check_new_invoices()]
  IF GMAIL_DEMO_MODE=true:
    return get_mock_invoices()  # 2-3 hardcoded dicts, no API call
  ELSE:
    Connect via simplegmail (OAuth credentials)
    Search: "after:{last_check_timestamp} has:attachment"
    For each matching email:
      Download PDF/image attachment bytes
      Call engine/invoice_parser.py → process_document()
      Add: origen="gmail", email_subject, email_date
    Return: list of processed_document dicts

[pages/1_Dashboard.py]
  For each returned invoice:
    save_to_ledger(invoice)
    st.toast("New invoice detected: {proveedor} — €{total}")
  
  Update: st.session_state["last_gmail_check"] = now.isoformat()
```

---

## 4. FP&A Calculation Flow

```
INPUT: data/ledger.csv + st.slider values (extra_ingresos, extra_gastos)

[pages/4_FPA.py]
  Load: get_cached_ledger() → df (full ledger)
  Filter: df[df["trimestre"] == selected_quarter] → df_quarter
  Filter: df ytd (all quarters in selected year up to current) → df_ytd

[engine/finance_engine.py → get_quarterly_summary(df_quarter)]
  Calculates:
    total_ingresos = sum(cuota_iva for tipo=ingreso rows)... (base_imponible)
    iva_cobrado = sum(cuota_iva for tipo=ingreso)
    iva_soportado_deducible = sum(cuota_iva_deducible for tipo=gasto)
    resultado_303 = iva_cobrado - iva_soportado_deducible
    beneficio_neto = total_ingresos - total_gastos_deducibles
    irpf_provision = beneficio_neto * 0.20

[pages/4_FPA.py — adjust with sliders]
  adj_iva_cobrado = iva_cobrado + (extra_ingresos × 0.21)
  adj_iva_soportado = iva_soportado_deducible + (extra_gastos × 0.21)
  adj_resultado_303 = adj_iva_cobrado - adj_iva_soportado
  adj_beneficio = (total_ingresos + extra_ingresos) - (total_gastos + extra_gastos)
  adj_irpf = adj_beneficio × 0.20

[engine/finance_engine.py → calculate_modelo_130(df_ytd)]
  beneficio_ytd = ingresos_ytd - gastos_deducibles_ytd
  pago_fraccionado = max(0, beneficio_ytd × 0.20)
  pago_neto = max(0, pago_fraccionado - retenciones_ytd)

OUTPUT: Rendered in st.expander() widgets — no data written to disk
```

---

## 5. Chatbot Context Flow

```
[pages/5_Chatbot.py — on every page render]

STEP 1: Build system prompt (changes every time ledger changes)
  get_cached_ledger() → df
  get_quarterly_summary(df, current_quarter) → summary
  json.dumps(user_profile) → profile_json
  json.dumps(summary) → summary_json
  
  system_prompt = base_role + "\n" + profile_json + "\n" + summary_json
  NOTE: system_prompt is rebuilt every render — always reflects latest ledger

STEP 2: Build messages array
  [{"role": m["role"], "content": m["content"]} 
   for m in st.session_state["messages"]]

STEP 3: API call
  anthropic.messages.create(
    model="claude-sonnet-4-6",
    system=system_prompt,      # Live context injected here
    messages=history,
    max_tokens=1000
  )

STEP 4: Update history
  st.session_state["messages"].append({"role": "user", "content": prompt})
  st.session_state["messages"].append({"role": "assistant", "content": reply})
  NOTE: History lives in session_state only — not persisted to disk

OUTPUT: Chat response rendered in st.chat_message() widget
        History grows in session_state until browser tab closes
```

---

## 6. Onboarding Data Flow

```
INPUT: User fills st.form() in pages/0_Onboarding.py

Fields collected → validated → assembled into profile dict:
  {
    nombre, actividad, iae_code, iva_regime, irpf_retencion_pct,
    work_location, home_office_pct, ss_bracket_monthly,
    tarifa_plana, tarifa_plana_end_date, alta_date,
    autonomia, onboarding_complete: true
  }

WRITE: json.dump(profile, open("data/user_profile.json", "w"))

LOAD INTO SESSION: st.session_state["user_profile"] = profile

NAVIGATE: st.switch_page("pages/1_Dashboard.py")

CONSUMED BY:
  - engine/tax_rules.py → classify_deductibility() 
      reads: work_location, home_office_pct
  - pages/5_Chatbot.py → build_system_prompt()
      reads: all fields (injected into Claude system prompt)
  - pages/0_Onboarding.py (never re-shown after onboarding_complete=true)
  - shared sidebar: reads nombre, alta_date for display
```

---

## 7. Language Switch Flow

```
TRIGGER: User clicks 🇪🇸 or 🇬🇧 button in sidebar

[i18n/__init__.py → set_lang("en" or "es")]
  st.session_state["lang"] = lang

st.rerun() called immediately

ON RERUN:
  Every t("key") call reads st.session_state["lang"]
  All strings re-rendered in new language
  Tooltips: only rendered if t("tax_terms.X_tooltip") is non-empty string
  Chatbot system prompt: "Always respond in {English|Spanish}"

DATA NOT AFFECTED:
  ledger.csv — never translated (raw financial data)
  user_profile.json — never translated (user's own inputs)
  tax_rules_2025.json — Spanish only (legal source, not displayed directly)
```

---

## 8. Data Transformation Summary Table

| Data Object | Enters As | Exits As | Transformed By |
|---|---|---|---|
| Invoice file | `bytes` | Row in `ledger.csv` | `invoice_parser` → `tax_rules` → `finance_engine` |
| OCR text | `str` (raw) | Structured `dict` | `parse_with_claude()` |
| Extracted fields | `dict` (raw) | `dict` + tax classifications | `classify_iva()` + `classify_deductibility()` |
| Ledger CSV | File on disk | `pd.DataFrame` in memory | `load_ledger()` |
| DataFrame | Full ledger | `dict` of aggregates | `get_quarterly_summary()` |
| DataFrame | Full ledger | `pd.DataFrame` (filtered+sorted) | `get_ar_aging()` |
| Calendly event | API JSON | Ledger draft `dict` | `generate_invoice_draft()` |
| User profile | `dict` | System prompt fragment | `build_system_prompt()` |
| Quarterly summary | `dict` | System prompt fragment | `build_system_prompt()` |
| Chat history | `list[dict]` | API messages array | `pages/5_Chatbot.py` |

---

## 9. What Is Never Stored

The following data is intentionally ephemeral:

- **OCR raw text** — discarded after Claude extracts fields. Never written to disk.
- **Chat history** — lives in `st.session_state["messages"]` only. Lost when tab closes.
- **What-if slider values** — Streamlit widget state only. Not persisted.
- **processed_document** — `st.session_state["processed_document"]` cleared after save.
- **Gmail OAuth tokens** — managed by simplegmail library, stored in its own credential cache (not our `data/` folder).
