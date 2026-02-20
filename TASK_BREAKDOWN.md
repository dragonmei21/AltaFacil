# TASK_BREAKDOWN.md — Alta Fácil Pro

> **What this document is:** The project split into atomic tasks, each small enough to be one Claude Code prompt. Work through them in order — each task builds on the previous one. Check off tasks as you complete them.
>
> **How to use with Claude Code:**
> 1. Open terminal in project root: `claude`
> 2. For each task, copy the prompt in the "Claude Code Prompt" block
> 3. Review the output, test it, check the box
> 4. Never skip a task — each one is a dependency of the next

---

## Phase 0 — Project Scaffolding (Do First)

### Task 0.1 — Create directory structure and config files
- [ ] **Status:** Doneee

**What to build:**
- All directories: `pages/`, `engine/`, `i18n/`, `data/`, `.streamlit/`
- `__init__.py` files for `engine/` and `i18n/`
- `.streamlit/config.toml` with exact theme values
- `.env.example`
- `.gitignore`
- Empty `requirements.txt` (will be filled)

**Claude Code Prompt:**
```
Create the complete directory structure for the Alta Fácil Pro project as defined in ARCHITECTURE.md Section 3.
Create all __init__.py files, .streamlit/config.toml with the theme from CLAUDE.md Section 8,
.env.example from CLAUDE.md Section 9, and .gitignore that excludes .env, credentials.json,
data/ledger.csv, data/user_profile.json, __pycache__, .venv, *.pyc, .DS_Store.
Do not create any Python source files yet.
```

**Verify:**
```bash
ls pages/ engine/ i18n/ data/ .streamlit/
cat .streamlit/config.toml    # Should show primaryColor = "#E94560"
```

---

### Task 0.2 — Create `data/tax_rules_2025.json`
- [ ] **Status:** doneee
**What to build:** The static tax rules file from CLAUDE.md Section 3.3.

**Claude Code Prompt:**
```
Create data/tax_rules_2025.json with the exact content from CLAUDE.md Section 3.3.
This is a static file — it will never be modified at runtime.
```

**Verify:**
```bash
python3 -c "import json; d=json.load(open('data/tax_rules_2025.json')); print(list(d['iva_rates'].keys()))"
# Expected: ['21', '10', '4', '0']
```

---

### Task 0.3 — Create `i18n/es.json` and `i18n/en.json`
- [ ] **Status:** doneee

**What to build:** Both JSON string files from CLAUDE.md Section 12.7 (es.json) and Section 12.8 (en.json). Include the `tax_verdicts` section from Section 12.6.

**Claude Code Prompt:**
```
Create i18n/es.json and i18n/en.json with the exact content from CLAUDE.md Sections 12.7 and 12.8.
Also add the "tax_verdicts" key to both files as defined in CLAUDE.md Section 12.6.
Verify that both files have identical top-level keys (same structure, different values).
```

**Verify:**
```bash
python3 -c "
import json
es = json.load(open('i18n/es.json'))
en = json.load(open('i18n/en.json'))
print('ES keys:', sorted(es.keys()))
print('EN keys:', sorted(en.keys()))
print('Match:', sorted(es.keys()) == sorted(en.keys()))
"
# Expected: Match: True
```

---

## Phase 1 — Engine Layer (Pure Python, No Streamlit)

### Task 1.1 — Build `i18n/__init__.py`
- [ ] **Status:** Not started

**What to build:** The `t()`, `get_lang()`, `set_lang()`, `tax_term()`, `tax_header()` functions from CLAUDE.md Section 12.2 and 12.5.

**Claude Code Prompt:**
```
Implement i18n/__init__.py with the exact function signatures and logic from CLAUDE.md Section 12.2.
Include t(), get_lang(), set_lang(), tax_term(), tax_header().
The t() function must support dot-notation keys and **kwargs for string formatting.
It must fall back to Spanish if a key is missing in English, and return the key itself if missing in both.
Export: __all__ = ["t", "get_lang", "set_lang", "LANGS", "LANG_LABELS", "DEFAULT_LANG", "tax_term", "tax_header"]
```

**Test:**
```bash
python3 -c "
import sys; sys.path.insert(0, '.')
# Simulate session state
import streamlit as st

# Test fallback
from i18n import t
# Should not crash even without streamlit running
print('i18n module imported successfully')
"
```

---

### Task 1.2 — Build `engine/tax_rules.py`
- [ ] **Status:** Not started

**What to build:** All functions from CLAUDE.md Section 5.1. This is the most critical engine module — must be 100% deterministic.

**Claude Code Prompt:**
```
Implement engine/tax_rules.py with all functions from CLAUDE.md Section 5.1:
load_tax_rules(), classify_iva(), classify_deductibility(),
calculate_modelo_303(), calculate_modelo_130(), get_cuota_ss().

Key requirements:
- classify_iva() must normalize input (lowercase, strip accents via unicodedata)
- classify_iva() checks rates in order: 4% → 10% → exempt(0%) → default 21%
- classify_deductibility() checks in order: exempt → vehicle(50%) → home(30% conditional) → non-deductible(0%) → professional(100%) → default 100% low confidence
- SS_BRACKETS and IRPF_BRACKETS constants defined at module level (from CLAUDE.md Section 4.3)
- No streamlit imports
- No pandas imports (tax_rules.py is pure Python)

Also include the IRPF_BRACKETS and SS_BRACKETS constants from CLAUDE.md Section 4.3.
```

**Test:**
```bash
python3 -c "
from engine.tax_rules import load_tax_rules, classify_iva, classify_deductibility, calculate_modelo_303
import pandas as pd

rules = load_tax_rules()
profile = {'work_location': 'casa', 'home_office_pct': 30}

# Test 1: Software → 21% general
r = classify_iva('hosting web mensual', 'OVH SAS', rules)
assert r['tipo_iva'] == 21, f'Expected 21, got {r[\"tipo_iva\"]}'
print('✅ Test 1 pass: software = 21%')

# Test 2: Restaurant → 10% reducido
r = classify_iva('comida con cliente', 'Restaurante El Patio', rules)
assert r['tipo_iva'] == 10, f'Expected 10, got {r[\"tipo_iva\"]}'
print('✅ Test 2 pass: restaurant = 10%')

# Test 3: Vehicle → 50% deductible
from engine.tax_rules import classify_deductibility
r = classify_deductibility('gasolina', 21, False, profile, rules)
assert r['porcentaje_deduccion'] == 50, f'Expected 50, got {r[\"porcentaje_deduccion\"]}'
print('✅ Test 3 pass: gasolina = 50%')

# Test 4: Electricity + home office → 30%
r = classify_deductibility('electricidad', 21, False, profile, rules)
assert r['porcentaje_deduccion'] == 30, f'Expected 30, got {r[\"porcentaje_deduccion\"]}'
print('✅ Test 4 pass: electricity + home office = 30%')

# Test 5: Empty DataFrame → zeros
df = pd.DataFrame(columns=['tipo','cuota_iva','cuota_iva_deducible'])
result = calculate_modelo_303(df)
assert result['a_pagar'] == 0.0
print('✅ Test 5 pass: empty ledger = zero 303')

print('All tax_rules tests passed.')
"
```

---

### Task 1.3 — Build `engine/finance_engine.py`
- [ ] **Status:** Not started

**What to build:** All functions from CLAUDE.md Section 5.3.

**Claude Code Prompt:**
```
Implement engine/finance_engine.py with all functions from CLAUDE.md Section 5.3:
load_ledger(), save_to_ledger(), get_current_quarter(), get_quarterly_summary(),
get_monthly_breakdown(), get_ar_aging(), get_ytd_summary().

Key requirements:
- load_ledger() creates data/ledger.csv with correct columns if not exists
- Enforce dtypes as specified in API_CONTRACTS.md Section 1.3
- save_to_ledger() generates UUID4 id, derives trimestre from fecha, fills defaults
- All summary functions return 0.0 (not NaN) for empty datasets
- get_monthly_breakdown() returns all 12 months even if no data
- No streamlit imports in this module
```

**Test:**
```bash
python3 -c "
from engine.finance_engine import load_ledger, save_to_ledger, get_current_quarter, get_quarterly_summary
import os

# Clean up any existing test data
if os.path.exists('data/ledger.csv'):
    os.rename('data/ledger.csv', 'data/ledger.csv.bak')

# Test 1: load empty ledger
df = load_ledger()
print(f'✅ Empty ledger loaded: {len(df)} rows, {len(df.columns)} columns')

# Test 2: save entry
entry = {
    'fecha': '2025-04-15', 'tipo': 'gasto', 'proveedor_cliente': 'AWS',
    'concepto': 'Hosting EC2', 'base_imponible': 100.0, 'tipo_iva': 21,
    'cuota_iva': 21.0, 'total': 121.0, 'deducible': True,
    'porcentaje_deduccion': 100, 'cuota_iva_deducible': 21.0,
    'aeat_articulo': 'Art. 28 LIRPF', 'estado': 'pendiente', 'origen': 'manual'
}
uid = save_to_ledger(entry)
print(f'✅ Entry saved with id: {uid[:8]}...')

# Test 3: reload and verify
df = load_ledger()
assert len(df) == 1
assert df.iloc[0]['proveedor_cliente'] == 'AWS'
print('✅ Entry persisted correctly')

# Test 4: quarterly summary
summary = get_quarterly_summary(df, '2025-Q2')
assert summary['total_gastos_deducibles'] == 100.0
print('✅ Quarterly summary correct')

# Restore backup
if os.path.exists('data/ledger.csv.bak'):
    os.rename('data/ledger.csv.bak', 'data/ledger.csv')

print('All finance_engine tests passed.')
"
```

---

### Task 1.4 — Build `engine/invoice_parser.py`
- [ ] **Status:** Not started

**What to build:** All functions from CLAUDE.md Section 5.2. This requires the Anthropic API key to be set.

**Claude Code Prompt:**
```
Implement engine/invoice_parser.py with all functions from CLAUDE.md Section 5.2:
preprocess_image(), extract_text_from_image(), extract_text_from_pdf(),
parse_with_claude(), process_document().

Key requirements:
- preprocess_image() must apply steps in exact order: grayscale → denoise(h=10) → Otsu threshold
- extract_text_from_pdf() tries pdfplumber first, falls back to OCR if text < 50 chars
- parse_with_claude() temperature=0, model=claude-haiku-4-5, max_tokens=500
- parse_with_claude() handles JSON parse errors gracefully (return {"parse_error": True, "raw": text})
- process_document() validates cuota_iva and flags discrepancy > €0.05
- process_document() raises ValueError if OCR produces < 20 chars
- No streamlit imports
```

**Test (requires ANTHROPIC_API_KEY in .env):**
```bash
python3 -c "
from dotenv import load_dotenv; load_dotenv()
import anthropic, os
from engine.invoice_parser import preprocess_image, parse_with_claude
import numpy as np

# Test 1: Image preprocessing doesn't crash
img = np.ones((100, 200, 3), dtype=np.uint8) * 200
processed = preprocess_image(img)
assert processed.shape[:2] == (100, 200)
assert processed.dtype == np.uint8
print('✅ preprocess_image works')

# Test 2: Claude extraction with fake text
client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
fake_text = '''
FACTURA
Amazon Web Services EMEA SARL
Fecha: 15/03/2025
Base imponible: 89,99 EUR
IVA 21%: 18,90 EUR
Total: 108,89 EUR
Concepto: Servicios de computacion en la nube
'''
result = parse_with_claude(fake_text, client)
print(f'✅ Claude extraction: proveedor={result.get(\"proveedor\", \"ERROR\")}')
print(f'   base_imponible={result.get(\"base_imponible\", \"ERROR\")}')
print(f'   tipo_iva={result.get(\"tipo_iva\", \"ERROR\")}')

print('invoice_parser tests passed.')
"
```

---

### Task 1.5 — Build `engine/gmail_watcher.py` (demo mode only)
- [ ] **Status:** Not started

**Claude Code Prompt:**
```
Implement engine/gmail_watcher.py with the check_new_invoices() function from CLAUDE.md Section 5.4.
Also implement get_mock_invoices() that returns 3 hardcoded realistic Spanish invoice dicts
in the process_document() output format (see API_CONTRACTS.md Section 1.1).

The mock invoices should be:
1. AWS hosting invoice: proveedor="Amazon Web Services", base=89.99, tipo_iva=21, deducible=True, pct=100
2. Renfe train ticket: proveedor="Renfe", base=45.00, tipo_iva=10, deducible=True, pct=100
3. Carrefour supermarket: proveedor="Carrefour", base=67.30, tipo_iva=21, deducible=False, pct=0

When GMAIL_DEMO_MODE=true in environment, check_new_invoices() returns get_mock_invoices().
No Gmail API call made in demo mode.
```

---

### Task 1.6 — Build `engine/calendly_client.py` (demo mode only)
- [ ] **Status:** Not started

**Claude Code Prompt:**
```
Implement engine/calendly_client.py with all functions from CLAUDE.md Section 5.5.
Also implement get_mock_events() returning 4 hardcoded Calendly event dicts:
1. "Strategy consultation" with Ana García, completed, €150
2. "UX audit" with Tech Startup SL, completed, €400
3. "Follow-up call" with Pedro López, active (upcoming), price=None
4. "Discovery call" with María Fernández, completed, €0 (free)

When CALENDLY_DEMO_MODE=true, get_scheduled_events() returns get_mock_events().
```

---

## Phase 2 — i18n Infrastructure

### Task 2.1 — Wire `i18n/__init__.py` with Streamlit session state
- [ ] **Status:** Not started

**Note:** Task 1.1 builds the pure Python i18n module. This task adds the Streamlit session state wiring and the `render_lang_switcher()` function.

**Claude Code Prompt:**
```
Add render_lang_switcher() to i18n/__init__.py as specified in CLAUDE.md Section 12.3.
This function renders two st.button() widgets (🇪🇸 ES and 🇬🇧 EN) side by side in the sidebar.
The active language button uses type="primary", inactive uses type="secondary".
Clicking either button calls set_lang() then st.rerun().

Important: render_lang_switcher() is the only function in i18n/ that imports streamlit.
All other i18n functions remain pure Python.
```

---

## Phase 3 — Streamlit App Shell

### Task 3.1 — Build `app.py`
- [ ] **Status:** Not started

**Claude Code Prompt:**
```
Implement app.py as specified in CLAUDE.md Section 6.1.
Requirements:
- st.set_page_config with correct title, icon, layout, initial_sidebar_state
- init_session_state() sets ALL keys from STATE_MANAGEMENT.md Section 2.1 with defaults
- Loads user_profile.json into st.session_state["user_profile"] if it exists
- If user_profile.json missing OR onboarding_complete=False: st.switch_page("pages/0_Onboarding.py")
- If onboarding complete: st.switch_page("pages/1_Dashboard.py")
- Load .env with python-dotenv at top of file
```

---

### Task 3.2 — Build shared `render_sidebar()` function
- [ ] **Status:** Not started

**Claude Code Prompt:**
```
Create a file shared/sidebar.py with the render_sidebar() function from CLAUDE.md Section 7.
This function:
1. Calls render_lang_switcher() from i18n FIRST (before anything else)
2. Shows user greeting with t("sidebar.greeting", name=...)
3. Shows two KPI metrics using t() for labels
4. Shows Gmail connection button / status
5. Shows Calendly token input + connect button
6. Uses t() for ALL strings — zero hardcoded strings

Also create shared/__init__.py (empty).

This function will be called at the top of every page file.
```

---

## Phase 4 — Streamlit Pages

### Task 4.1 — Build `pages/0_Onboarding.py`
- [ ] **Status:** Not started

**Claude Code Prompt:**
```
Implement pages/0_Onboarding.py from CLAUDE.md Section 6.2.
Requirements:
- Import and call render_sidebar() from shared.sidebar at top
- All widgets inside a single st.form("onboarding_form")
- Work location selector uses st.radio(horizontal=True) — this is a NEW WIDGET requirement
- IRPF retention uses st.select_slider() — NEW WIDGET requirement
- Show home_office_pct slider only when work_location != "En oficina/coworking"
- Validate: nombre and actividad must not be empty
- On success: write data/user_profile.json, set st.session_state["user_profile"], st.switch_page("pages/1_Dashboard.py")
- Use t() for ALL strings
```

---

### Task 4.2 — Build `pages/1_Dashboard.py`
- [ ] **Status:** Not started

**Claude Code Prompt:**
```
Implement pages/1_Dashboard.py from CLAUDE.md Section 6.3.
Requirements:
- 4 KPI cards using st.metric() with delta parameter — NEW WIDGET
- Plotly grouped bar chart (revenue, expenses, tax provision) with dark theme
- st.dataframe() with color-coded rows (style.apply)
- Gmail toast notifications using st.toast() — NEW WIDGET
- Guard: only poll Gmail if should_poll_gmail() (15+ minutes since last check)
- @st.cache_data(ttl=30) on ledger load
- Use t() for ALL strings including chart axis labels and legend
```

---

### Task 4.3 — Build `pages/2_Scanner.py` (Core Feature)
- [ ] **Status:** Not started

**This is the most complex page. Build it last among the pages.**

**Claude Code Prompt:**
```
Implement pages/2_Scanner.py from CLAUDE.md Section 6.4.
This is the core feature — implement it completely.

NEW WIDGETS required (from assignment checklist):
- st.radio(horizontal=True) for method selection
- st.camera_input() for photo capture

Requirements:
- Three input methods: upload, camera, manual form
- Process button triggers process_document() inside st.spinner()
- Results shown in 3 columns: extracted data (st.metric cards), verdict (st.success/warning/error), edit expander
- IVA discrepancy check with st.warning if mismatch > €0.05
- Save button → save_to_ledger() → st.cache_data.clear() → st.balloons() → st.success()
- Clear st.session_state["processed_document"] after save
- Recent entries table at bottom with color coding
- Use t() for ALL strings
- Handle invoice_draft from session_state if pre-filled from Calendly
```

---

### Task 4.4 — Build `pages/4_FPA.py`
- [ ] **Status:** Not started

**Claude Code Prompt:**
```
Implement pages/4_FPA.py from CLAUDE.md Section 6.6.
Requirements:
- Two st.slider() widgets for what-if simulation — must recalculate ALL numbers in real time
- Modelo 303 in st.expander(expanded=True): show IVA cobrado, soportado, resultado with color
- Modelo 130 in st.expander(expanded=True): YTD calculation with retenciones
- Deadline countdown: st.progress() + st.metric() — use tax_header() for section titles
- Quarter selector in sidebar using st.selectbox()
- All numbers update instantly when sliders move (no button needed — Streamlit reruns on slider change)
- Use t() and tax_header() for ALL strings
```

---

### Task 4.5 — Build `pages/5_Chatbot.py`
- [ ] **Status:** Not started

**Claude Code Prompt:**
```
Implement pages/5_Chatbot.py from CLAUDE.md Section 6.7.

NEW WIDGETS required:
- st.chat_message() for bubble display
- st.chat_input() for text input

Requirements:
- System prompt rebuilt on every render using latest ledger data (always fresh)
- Language injected into system prompt: "Always respond in {English|Spanish}"
- Show 3 suggestion buttons if no messages yet (using t() for suggestion text)
- st.chat_input() at bottom with t("chatbot.placeholder")
- On submit: append user message, call Claude claude-sonnet-4-6, append assistant message
- st.info() disclaimer at top using t("chatbot.disclaimer")
- @st.cache_resource for Claude client
- Use t() for ALL strings
```

---

### Task 4.6 — Build `pages/3_AR_Agenda.py`
- [ ] **Status:** Not started

**Claude Code Prompt:**
```
Implement pages/3_AR_Agenda.py from CLAUDE.md Section 6.5.
Requirements:
- Three st.tabs(): upcoming, issued invoices, AR aging
- In demo mode: load from get_mock_events()
- AR aging table: color-coded by bucket (green, yellow, orange, red)
- "Generate invoice" button for completed events → sets st.session_state["invoice_draft"] → st.switch_page to Scanner
- Use t() for ALL strings
```

---

## Phase 5 — Integration and Testing

### Task 5.1 — Create `data/tax_rules_2025.json` test suite
- [ ] **Status:** Not started

**Claude Code Prompt:**
```
Create tests/test_tax_rules.py with unit tests covering:
1. All IVA rate classifications (at least 3 examples per rate)
2. All deductibility classifications (vehicle 50%, home 30% with casa/oficina/mixto profiles, professional 100%, non-deductible 0%)
3. Modelo 303 calculation with known values
4. Modelo 130 calculation with known values
5. SS bracket lookup (at least 5 income levels including tarifa plana)
6. Edge cases: empty concepto, concepto with accents, very long concepto

Run with: python -m pytest tests/test_tax_rules.py -v
```

---

### Task 5.2 — Create `tests/test_finance_engine.py`
- [ ] **Status:** Not started

**Claude Code Prompt:**
```
Create tests/test_finance_engine.py with unit tests covering:
1. load_ledger() creates empty file with correct columns if not exists
2. save_to_ledger() generates unique UUID each call
3. save_to_ledger() correctly derives trimestre from fecha
4. get_current_quarter() correct for all 4 quarters
5. get_quarterly_summary() returns zeros for empty DataFrame (no NaN)
6. get_monthly_breakdown() returns all 12 months
7. get_ar_aging() correctly buckets by days outstanding

Use a temp file for ledger to avoid touching real data.
```

---

### Task 5.3 — i18n completeness check
- [ ] **Status:** Not started

**Claude Code Prompt:**
```
Create tests/test_i18n.py that:
1. Loads es.json and en.json
2. Verifies they have identical top-level keys
3. Recursively verifies all nested keys match
4. Verifies no empty string values in es.json (every Spanish string must be present)
5. Verifies tax_verdicts keys are present in both files
6. Prints a report of any missing keys

Run with: python -m pytest tests/test_i18n.py -v
```

---

### Task 5.4 — Full integration smoke test
- [ ] **Status:** Not started

**Claude Code Prompt:**
```
Create tests/test_integration.py with an end-to-end test:
1. Start with empty ledger (temp file)
2. Load fake OCR text through parse_with_claude() → classify_iva() → classify_deductibility()
3. Call save_to_ledger() with the result
4. Call get_quarterly_summary() and verify IVA values are correct
5. Call calculate_modelo_303() and verify resultado = iva_cobrado - iva_soportado_deducible

This test requires ANTHROPIC_API_KEY in environment.
Mark with @pytest.mark.integration so it can be skipped in CI.
```

---

## Phase 6 — Demo Preparation

### Task 6.1 — Create `README.md`
- [ ] **Status:** Not started

**Claude Code Prompt:**
```
Create README.md for the GitHub repository with:
1. Project description (2-3 sentences)
2. Screenshot placeholder
3. Setup instructions (condensed from ENVIRONMENT.md)
4. How to run
5. Architecture overview (1 paragraph referencing ARCHITECTURE.md)
6. Assignment context: PDAI Assignment 1, ESADE

Keep it under 100 lines. Clean, professional.
```

---

### Task 6.2 — Seed demo data
- [ ] **Status:** Not started

**Claude Code Prompt:**
```
Create scripts/seed_demo_data.py that:
1. Creates a realistic demo user_profile.json (María García, consultora de marketing, casa, tarifa plana ended)
2. Creates a ledger.csv with 15 realistic entries:
   - 8 gastos across Q1 and Q2 2025 (AWS hosting, Notion, Formación Python, Renfe, coworking, electricidad, gasolina, gestor)
   - 7 ingresos in Q1 and Q2 2025 (3 paid, 4 pending)
3. All amounts are realistic for a Spanish marketing consultant
4. Mix of deductible/non-deductible entries

Run with: python scripts/seed_demo_data.py
```

---

### Task 6.3 — Final wiring check
- [ ] **Status:** Not started

**Claude Code Prompt:**
```
Review the entire codebase for:
1. Any hardcoded Spanish or English strings in page files (should all use t())
2. Any engine module that imports streamlit (should be none)
3. Any page that imports from another page (should be none)
4. Any st.session_state["key"] access without .get() default (potential KeyError)
5. Any place where cuota_iva is not recalculated from base_imponible

Fix any violations found. Report what was changed.
```

---

## Completion Checklist

Before submitting the assignment:

- [ ] `streamlit run app.py` starts without errors on fresh clone
- [ ] Onboarding completes and saves `data/user_profile.json`
- [ ] Scanner: upload a PDF → correct extraction → correct IVA classification → saves to ledger
- [ ] Scanner: camera input works (test in mobile browser)
- [ ] Dashboard KPIs update after scanner save
- [ ] FP&A sliders move and all numbers update in real time
- [ ] Chatbot responds in Spanish when lang=es
- [ ] Chatbot responds in English when lang=en
- [ ] Language toggle switches ALL strings instantly
- [ ] Tax terms show tooltips in English mode, no tooltips in Spanish mode
- [ ] All pytest tests pass: `python -m pytest tests/ -v`
- [ ] No hardcoded strings: `grep -r 'st\.title\("' pages/` returns nothing
- [ ] GitHub repo has: `app.py`, `pages/`, `engine/`, `i18n/`, `requirements.txt`, `README.md`, `.env.example`
- [ ] Loom video recorded (4 minutes covering all 6 screens)
- [ ] 2-page process document written
