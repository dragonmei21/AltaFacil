# Alta Fácil Pro — Claude Code Execution Plan

> **Purpose of this file:** This is the authoritative technical specification for building the Alta Fácil Pro Streamlit app. Every function signature, widget choice, data schema, and business rule is defined here. When generating code, follow this document exactly. Do not invent alternatives unless a section explicitly says "optional".

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [File Structure](#2-file-structure)
3. [Data Schemas](#3-data-schemas)
4. [Spanish Tax Rules — Source of Truth](#4-spanish-tax-rules--source-of-truth)
5. [Engine Layer — Function Signatures & Logic](#5-engine-layer--function-signatures--logic)
6. [Streamlit Pages — Widget-by-Widget Spec](#6-streamlit-pages--widget-by-widget-spec)
7. [Shared Sidebar](#7-shared-sidebar)
8. [Streamlit Configuration](#8-streamlit-configuration)
9. [Environment Variables](#9-environment-variables)
10. [Dependencies](#10-dependencies)
11. [Code Patterns & Constraints](#11-code-patterns--constraints)
12. [Internationalisation (i18n) — Bilingual ES/EN](#12-internationalisation-i18n--bilingual-esen)

---

## 1. Project Overview

**Product:** Alta Fácil Pro — AI-powered junior accountant for Spanish autónomos (freelancers).

**Core value proposition:** User uploads/photographs an expense invoice → OCR + Claude extracts all fields → Spanish tax rules engine classifies IVA rate and deductibility → entry saved to live ledger → FP&A screen shows real-time quarterly tax projection → chatbot answers tax questions using real user data.

**Stack summary:**
- Frontend: Streamlit (multi-page app)
- AI extraction: pytesseract (OCR) + OpenCV (preprocessing) + Claude claude-haiku-4-5 (structured extraction)
- Tax engine: deterministic Python rules (NOT RAG, NOT LLM — see Section 4)
- Chatbot: Claude claude-sonnet-4-6 with dynamic system prompt containing live ledger data
- Persistence: CSV (ledger) + JSON (user profile) — no database
- Charts: Plotly Express
- External: Gmail API (simplegmail) + Calendly REST API v2

**Language:** Python 3.11+

**Run command:** `streamlit run app.py`

---

## 2. File Structure

```
altafacil_pro/
├── app.py                        # Entry point. Handles routing + session init.
├── pages/
│   ├── 0_Onboarding.py           # First-run user profile quiz
│   ├── 1_Dashboard.py            # Live KPI cards + cashflow chart
│   ├── 2_Scanner.py              # AI invoice/receipt scanner — CORE FEATURE
│   ├── 3_AR_Agenda.py            # Calendly bookings → AR tracking
│   ├── 4_FPA.py                  # FP&A: Modelo 303/130 simulation + sliders
│   └── 5_Chatbot.py              # El Gestor AI chatbot
├── engine/
│   ├── __init__.py               # Empty
│   ├── invoice_parser.py         # OCR + Claude extraction pipeline
│   ├── tax_rules.py              # Spanish IVA + IRPF + SS rules engine
│   ├── finance_engine.py         # Ledger CRUD + FP&A calculations
│   ├── gmail_watcher.py          # Gmail API polling
│   └── calendly_client.py        # Calendly REST API
├── i18n/
│   ├── __init__.py               # Exports t(), get_lang(), LANGS
│   ├── es.json                   # Spanish strings (canonical/source language)
│   └── en.json                   # English strings (full translation of es.json)
├── data/
│   ├── ledger.csv                # Created on first run if missing
│   ├── user_profile.json         # Created during onboarding
│   └── tax_rules_2025.json       # Static — never overwritten at runtime
├── .streamlit/
│   └── config.toml               # Theme + server config
├── .env                          # API keys — never commit
├── .env.example                  # Template — commit this
├── requirements.txt
└── README.md
```

---

## 3. Data Schemas

### 3.1 `data/ledger.csv` — Column Definitions

| Column | Type | Values / Format | Notes |
|---|---|---|---|
| `id` | str | UUID4 | Generated at save time |
| `fecha` | str | `YYYY-MM-DD` | Invoice/transaction date |
| `tipo` | str | `"gasto"` \| `"ingreso"` | AP vs AR |
| `proveedor_cliente` | str | Free text | Vendor name (gasto) or client name (ingreso) |
| `nif` | str | Free text, nullable | NIF/CIF of vendor/client |
| `concepto` | str | Free text | Short description of service/product |
| `numero_factura` | str | Free text, nullable | Invoice number |
| `base_imponible` | float | Positive | Pre-tax amount |
| `tipo_iva` | int | `0`, `4`, `10`, `21` | IVA percentage applied |
| `cuota_iva` | float | Positive | base_imponible × tipo_iva / 100 |
| `total` | float | Positive | base_imponible + cuota_iva |
| `deducible` | bool | `True` \| `False` | Is IVA soportado deductible? |
| `porcentaje_deduccion` | int | `0`, `30`, `50`, `100` | % of cuota_iva deductible |
| `cuota_iva_deducible` | float | Positive | cuota_iva × porcentaje_deduccion / 100 |
| `aeat_articulo` | str | e.g. `"Art. 90.Uno"` | Legal justification |
| `trimestre` | str | `"2025-Q1"` format | Derived from fecha |
| `estado` | str | `"pendiente"` \| `"pagado"` \| `"vencido"` | Payment status |
| `origen` | str | `"scanner"` \| `"gmail"` \| `"calendly"` \| `"manual"` | How entry was created |

**Initialize empty ledger:**
```python
LEDGER_COLUMNS = [
    "id", "fecha", "tipo", "proveedor_cliente", "nif", "concepto",
    "numero_factura", "base_imponible", "tipo_iva", "cuota_iva", "total",
    "deducible", "porcentaje_deduccion", "cuota_iva_deducible", "aeat_articulo",
    "trimestre", "estado", "origen"
]
```

### 3.2 `data/user_profile.json` — Schema

```json
{
  "nombre": "string",
  "actividad": "string — e.g. 'Consultoría de marketing'",
  "iae_code": "string — e.g. '702'",
  "iva_regime": "general | simplificado | exento",
  "irpf_retencion_pct": 15,
  "work_location": "casa | oficina | mixto",
  "home_office_pct": 30,
  "ss_bracket_monthly": 200,
  "tarifa_plana": true,
  "tarifa_plana_end_date": "YYYY-MM-DD | null",
  "alta_date": "YYYY-MM-DD",
  "autonomia": "peninsular | canarias | ceuta_melilla",
  "onboarding_complete": true
}
```

### 3.3 `data/tax_rules_2025.json` — Structure

```json
{
  "version": "2025-07-31",
  "source": "AEAT Tipos impositivos en el IVA 2025 — Ley 37/1992",
  "iva_rates": {
    "21": {
      "label": "Tipo general",
      "article": "Art. 90.Uno Ley 37/1992",
      "keywords": ["software", "saas", "hosting", "marketing", "publicidad",
                   "consultoría", "consulting", "telecom", "telefonia", "internet",
                   "coworking", "diseño", "electricidad", "luz", "gas",
                   "seguros", "peluquería", "gimnasio", "restaurante_alcohol"]
    },
    "10": {
      "label": "Tipo reducido",
      "article": "Art. 91.Uno Ley 37/1992",
      "keywords": ["transporte", "hostelería", "hotel", "restaurante", "catering",
                   "obra", "reforma", "vivienda", "cine", "teatro", "museo",
                   "agua", "medicamento_veterinario"]
    },
    "4": {
      "label": "Tipo superreducido",
      "article": "Art. 91.Dos Ley 37/1992",
      "keywords": ["pan", "harina", "leche", "queso", "huevos", "fruta",
                   "verdura", "legumbre", "cereal", "aceite oliva", "aceite de oliva",
                   "medicamento", "medicamentos", "libro", "libros",
                   "periodico", "revista", "preservativo", "tampón", "compresa"]
    },
    "0": {
      "label": "Exento",
      "article": "Art. 20 Ley 37/1992",
      "keywords": ["educación", "formación reglada", "médico", "médica",
                   "psicólogo", "fisioterapeuta", "alquiler vivienda",
                   "seguro medico", "seguro médico"]
    }
  },
  "deductibility_rules": {
    "full_100": {
      "article": "Art. 28-30 Ley 35/2006 IRPF",
      "keywords": ["software", "saas", "hosting", "dominio", "marketing",
                   "publicidad", "formación", "curso", "asesoría", "gestoría",
                   "contabilidad", "notaría", "registro", "coworking",
                   "material oficina", "papelería", "suscripción profesional"]
    },
    "partial_50": {
      "article": "Art. 95.Tres Ley 37/1992 LIVA",
      "keywords": ["vehículo", "coche", "moto", "gasolina", "combustible",
                   "parking", "mantenimiento vehículo", "seguro coche"],
      "pct": 50
    },
    "partial_home": {
      "article": "Art. 30 Ley 35/2006 IRPF",
      "keywords": ["electricidad", "luz", "agua", "gas", "internet", "fibra",
                   "alquiler", "hipoteca", "comunidad"],
      "pct": 30,
      "condition": "work_location == 'casa' or work_location == 'mixto'"
    },
    "zero_0": {
      "article": "Art. 28 Ley 35/2006 IRPF — no deducible",
      "keywords": ["ropa", "moda", "supermercado", "alimentación personal",
                   "ocio", "viaje vacaciones", "regalo personal"],
      "pct": 0
    }
  }
}
```

---

## 4. Spanish Tax Rules — Source of Truth

> **CRITICAL:** The tax rules engine must be deterministic. Never use an LLM to decide IVA rates or deductibility percentages. LLM output for legal/financial decisions is unacceptable. The engine classifies → Claude only fills gaps for unknown keywords.

### 4.1 IVA Rate Rules (from AEAT, Ley 37/1992)

| Rate | Legal Basis | Key Categories for Autónomos |
|---|---|---|
| **21%** | Art. 90.Uno | Software/SaaS, hosting, marketing, consulting, coworking, telecom, electricity, gas, most professional services |
| **10%** | Art. 91.Uno | Transport of passengers, restaurants/hostelería, construction on residential buildings, water supply, museum/cinema/theatre entry |
| **4%** | Art. 91.Dos | Raw unprocessed foods (bread, milk, eggs, fresh fruit/veg, olive oil), human medicines, books/newspapers (including digital), tampons/preservatives |
| **Exempt** | Art. 20 | Regulated education, regulated health services, residential rental — these appear on invoices with NO IVA line |

> **Important distinctions:**
> - `tipo_iva = 0` with `exempt = True` → no IVA line on invoice, cannot deduct IVA soportado
> - `tipo_iva = 0` with `exempt = False` → zero-rated, CAN deduct IVA soportado (rare for autónomos)
> - Canarias: IGIC 7% instead of IVA. If `autonomia == "canarias"` in user profile, display IGIC label but use same deductibility logic.

### 4.2 Deductibility Rules (from IRPF Ley 35/2006 + LIVA)

| Category | % Deductible | Legal Basis | Condition |
|---|---|---|---|
| Professional services (software, hosting, marketing, gestoría, formación, coworking, office supplies) | 100% | Art. 28-30 Ley 35/2006 | Must be exclusively professional use |
| Vehicles (purchase, fuel, insurance, maintenance) | 50% | Art. 95.Tres LIVA | Cannot exceed 50% unless exclusive professional use proven |
| Home office expenses (electricity, internet, water, rent) | 30% | Art. 30 Ley 35/2006 | Only if `work_location` is `"casa"` or `"mixto"` in user profile |
| Client meals | 100% up to €26.67/day domestic | Art. 9 Reglamento IRPF | Must be demonstrably business-related |
| Personal clothing | 0% | Art. 28 Ley 35/2006 | Exception: uniforms/PPE are 100% |
| Personal food/gym/leisure | 0% | Art. 28 Ley 35/2006 | Exception: gym is 100% if user is a fitness professional |

### 4.3 Tax Calculation Formulas

```python
# Modelo 303 (quarterly VAT)
resultado_303 = iva_cobrado_trimestre - iva_soportado_deducible_trimestre
a_pagar_303 = max(0, resultado_303)
a_compensar_303 = abs(min(0, resultado_303))

# Modelo 130 (quarterly IRPF payment)
beneficio_acumulado = ingresos_acumulado_ytd - gastos_deducibles_acumulado_ytd
pago_fraccionado_130 = max(0, beneficio_acumulado * 0.20)
# Note: subtract retenciones already withheld (IRPF 15% on client invoices)
pago_neto_130 = max(0, pago_fraccionado_130 - retenciones_cobradas_ytd)

# IRPF annual brackets 2025
IRPF_BRACKETS = [
    (0, 12450, 0.19),
    (12450, 20200, 0.24),
    (20200, 35200, 0.30),
    (35200, 60000, 0.37),
    (60000, float('inf'), 0.45),
]

# Social Security (RETA 2025) — 15 brackets
SS_BRACKETS = [
    (0, 670, 200),
    (670, 900, 275),
    (900, 1166.70, 291),
    (1166.70, 1300, 294),
    (1300, 1500, 350),
    (1500, 1700, 370),
    (1700, 1850, 390),
    (1850, 2030, 415),
    (2030, 2330, 490),
    (2330, 2760, 530),
    (2760, 3190, 610),
    (3190, 3620, 700),
    (3620, 4050, 850),
    (4050, 6000, 1000),
    (6000, float('inf'), 1267),
]
# Each tuple: (net_income_from, net_income_to, monthly_cuota_eur)
# Tarifa plana (first 12 months): cuota = €80/month regardless of bracket
```

---

## 5. Engine Layer — Function Signatures & Logic

### 5.1 `engine/tax_rules.py`

```python
import json
from pathlib import Path

def load_tax_rules() -> dict:
    """Load tax_rules_2025.json. Called once, cached with @st.cache_data."""
    path = Path("data/tax_rules_2025.json")
    with open(path) as f:
        return json.load(f)

def classify_iva(concepto: str, proveedor: str, rules: dict) -> dict:
    """
    Classify IVA rate for an expense/invoice.
    
    Args:
        concepto: Short description of the service/product (from invoice)
        proveedor: Vendor name (from invoice)
        rules: Output of load_tax_rules()
    
    Returns:
        {
            "tipo_iva": int,          # 0, 4, 10, or 21
            "label": str,             # Human-readable rate name
            "article": str,           # AEAT legal article
            "exempt": bool,           # True if Art. 20 exempt (no IVA line)
            "confidence": str,        # "high" | "low"
            "match_keyword": str      # The keyword that triggered the match
        }
    
    Logic:
        1. Normalize input: lowercase, strip accents, strip punctuation
        2. Check keywords in order: 4% → 10% → exempt → fallback 21%
        3. If no keyword match: return 21% with confidence="low"
        4. Never call Claude from this function — deterministic only
    """

def classify_deductibility(
    concepto: str,
    tipo_iva: int,
    exempt: bool,
    user_profile: dict,
    rules: dict
) -> dict:
    """
    Classify deductibility of IVA soportado.
    
    Args:
        concepto: Service/product description
        tipo_iva: IVA rate (0, 4, 10, 21)
        exempt: True if exempt (Art. 20) — if True, pct is always 0
        user_profile: Loaded from user_profile.json
        rules: Output of load_tax_rules()
    
    Returns:
        {
            "deducible": bool,
            "porcentaje_deduccion": int,   # 0, 30, 50, or 100
            "cuota_iva_deducible": float,  # cuota_iva * porcentaje / 100
            "justification": str,          # Human-readable explanation
            "article": str                 # AEAT legal article
        }
    
    Logic:
        1. If exempt=True: return 0%, "IVA exento — no deducible"
        2. Check vehicle keywords → 50%
        3. Check home keywords + user_profile["work_location"] → 30% if casa/mixto, else 0%
        4. Check non-deductible keywords → 0%
        5. Check professional keywords → 100%
        6. Default: 100% with confidence="low" + show disclaimer
    """

def calculate_modelo_303(df_quarter: "pd.DataFrame") -> dict:
    """
    Calculate Modelo 303 for a given quarter's ledger data.
    
    Args:
        df_quarter: Filtered DataFrame for the quarter (already filtered by trimestre)
    
    Returns:
        {
            "iva_cobrado": float,              # Sum of cuota_iva for tipo=ingreso
            "iva_soportado_total": float,      # Sum of cuota_iva for tipo=gasto
            "iva_soportado_deducible": float,  # Sum of cuota_iva_deducible for tipo=gasto
            "resultado": float,                # iva_cobrado - iva_soportado_deducible
            "a_pagar": float,                  # max(0, resultado)
            "a_compensar": float,              # abs(min(0, resultado))
        }
    """

def calculate_modelo_130(df_ytd: "pd.DataFrame", retenciones_ytd: float = 0) -> dict:
    """
    Calculate Modelo 130 pago fraccionado.
    
    Args:
        df_ytd: All ledger entries from start of year to end of current quarter
        retenciones_ytd: Total IRPF retenciones already withheld by clients YTD
    
    Returns:
        {
            "ingresos_ytd": float,
            "gastos_deducibles_ytd": float,
            "beneficio_ytd": float,
            "pago_fraccionado_bruto": float,   # beneficio_ytd * 0.20
            "retenciones_ytd": float,
            "pago_neto": float,                # max(0, bruto - retenciones)
        }
    """

def get_cuota_ss(net_monthly_income: float, tarifa_plana: bool, tarifa_plana_active: bool) -> float:
    """
    Get monthly Social Security cuota from RETA 2025 brackets.
    
    Args:
        net_monthly_income: Estimated monthly net income
        tarifa_plana: Whether user applied for tarifa plana
        tarifa_plana_active: Whether tarifa plana period is still active
    
    Returns:
        Monthly cuota in EUR
    
    Logic:
        If tarifa_plana and tarifa_plana_active: return 80.0
        Else: iterate SS_BRACKETS, return cuota for matching bracket
    """
```

### 5.2 `engine/invoice_parser.py`

```python
import cv2
import numpy as np
import pytesseract
import pdfplumber
from PIL import Image
import anthropic
import json
import io
from pathlib import Path

def preprocess_image(img: np.ndarray) -> np.ndarray:
    """
    Preprocess image for OCR. Apply in this exact order:
    1. Convert to grayscale: cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    2. Denoise: cv2.fastNlMeansDenoising(gray, h=10, templateWindowSize=7, searchWindowSize=21)
    3. Threshold: cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    Returns: thresholded binary image (np.ndarray)
    """

def extract_text_from_image(file_bytes: bytes) -> str:
    """
    Run OCR on image bytes.
    1. Convert bytes to PIL Image → np.ndarray
    2. Call preprocess_image()
    3. pytesseract.image_to_string(processed, lang='spa+eng', config='--psm 6')
    Returns: raw OCR text string
    """

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract text from PDF.
    1. Try pdfplumber first: open BytesIO, extract text from all pages
    2. If extracted text length < 50 chars: fall back to pdf2image → OCR each page
    3. Concatenate all page texts with newline separator
    Returns: full text string
    """

def parse_with_claude(raw_text: str, client: anthropic.Anthropic) -> dict:
    """
    Send OCR text to Claude claude-haiku-4-5 for structured extraction.
    
    System prompt:
        "Eres un experto en facturas españolas. Extrae los campos solicitados 
         con precisión. Devuelve SOLO JSON válido, sin texto adicional, 
         sin backticks, sin explicaciones."
    
    User prompt:
        f"Del siguiente texto de una factura española, extrae en JSON:
        - proveedor (string): nombre del vendedor/empresa
        - nif_proveedor (string|null): NIF o CIF del proveedor
        - fecha (string): fecha en formato YYYY-MM-DD
        - numero_factura (string|null): número de factura
        - base_imponible (float): importe sin IVA
        - tipo_iva (int): porcentaje de IVA (0, 4, 10, o 21)
        - cuota_iva (float): importe del IVA
        - total (float): importe total
        - concepto (string): descripción breve del servicio o producto
        - tipo_documento (string): 'factura', 'ticket', 'recibo', u 'otro'
        
        Texto:
        {raw_text}"
    
    Model: claude-haiku-4-5
    max_tokens: 500
    temperature: 0 (must be deterministic)
    
    Returns: parsed dict. On JSON parse error: return {"error": str(e), "raw": response_text}
    """

def process_document(
    file_bytes: bytes,
    file_type: str,       # "pdf" | "image"
    user_profile: dict,
    tax_rules: dict,
    claude_client: anthropic.Anthropic
) -> dict:
    """
    Master function — orchestrates full pipeline.
    
    Returns:
        {
            # From Claude extraction:
            "proveedor": str,
            "nif_proveedor": str | None,
            "fecha": str,
            "numero_factura": str | None,
            "base_imponible": float,
            "tipo_iva": int,
            "cuota_iva": float,
            "total": float,
            "concepto": str,
            "tipo_documento": str,
            
            # From tax engine (classify_iva):
            "iva_label": str,
            "iva_article": str,
            "iva_confidence": str,
            "exempt": bool,
            
            # From tax engine (classify_deductibility):
            "deducible": bool,
            "porcentaje_deduccion": int,
            "cuota_iva_deducible": float,
            "deductibility_justification": str,
            "deductibility_article": str,
            
            # Pipeline metadata:
            "extraction_method": str,      # "pdfplumber" | "tesseract" | "claude_only"
            "parse_error": bool,           # True if Claude returned malformed JSON
        }
    
    Error handling:
        - If OCR produces < 20 chars: raise ValueError("OCR failed — image quality too low")
        - If Claude returns malformed JSON: return dict with parse_error=True and raw text
        - Never crash silently — always surface errors to UI
    """
```

### 5.3 `engine/finance_engine.py`

```python
import pandas as pd
import uuid
from datetime import datetime, date
from pathlib import Path

LEDGER_PATH = Path("data/ledger.csv")
LEDGER_COLUMNS = [...]  # as defined in Section 3.1

def load_ledger() -> pd.DataFrame:
    """
    Load ledger.csv. Create with correct columns if not exists.
    Use @st.cache_data(ttl=30) on calling code (not here — engine is pure).
    Returns: DataFrame with correct dtypes.
    Dtypes: base_imponible/cuota_iva/total/cuota_iva_deducible → float64,
            tipo_iva/porcentaje_deduccion → int64,
            deducible → bool,
            fecha → keep as str (format is YYYY-MM-DD)
    """

def save_to_ledger(entry: dict) -> str:
    """
    Append one entry to ledger.csv.
    
    Args:
        entry: dict with all LEDGER_COLUMNS keys.
               Missing keys → fill with defaults (id=uuid4, trimestre=derived from fecha,
               estado="pendiente")
    
    Returns: The generated UUID id string.
    
    Side effects:
        - Appends to ledger.csv
        - MUST call st.cache_data.clear() after saving to invalidate Streamlit cache
    """

def get_current_quarter(d: date = None) -> str:
    """
    Return quarter string for a date.
    e.g. date(2025, 4, 15) → "2025-Q2"
    If d is None: use today.
    """

def get_quarterly_summary(df: pd.DataFrame, quarter: str) -> dict:
    """
    Args:
        df: Full ledger DataFrame
        quarter: e.g. "2025-Q2"
    
    Returns:
        {
            "total_ingresos": float,
            "total_gastos_base": float,          # sum of base_imponible for gastos
            "total_gastos_deducibles": float,    # sum of base_imponible for gastos where deducible=True
            "iva_cobrado": float,                # sum of cuota_iva for ingresos
            "iva_soportado_deducible": float,    # sum of cuota_iva_deducible for gastos
            "resultado_303": float,              # iva_cobrado - iva_soportado_deducible
            "beneficio_neto": float,             # total_ingresos - total_gastos_deducibles
            "irpf_provision": float,             # beneficio_neto * 0.20 (simplified)
            "n_facturas": int,
            "n_gastos": int,
        }
    """

def get_monthly_breakdown(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """
    Returns DataFrame with columns: month (1-12), ingresos, gastos_base, tax_provision
    For use in Plotly bar chart.
    tax_provision = (ingresos - gastos) * 0.20 as monthly running estimate.
    """

def get_ar_aging(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter ingresos with estado != 'pagado'.
    Calculate days_outstanding = today - fecha.
    Add column 'aging_bucket': '0-30' | '31-60' | '61-90' | '90+'
    Return sorted by fecha ascending (oldest first).
    """

def get_ytd_summary(df: pd.DataFrame, year: int, through_quarter: int) -> dict:
    """
    Return YTD totals from Q1 through through_quarter (inclusive).
    Used for Modelo 130 cumulative calculation.
    Same structure as get_quarterly_summary() but across multiple quarters.
    """
```

### 5.4 `engine/gmail_watcher.py`

```python
def check_new_invoices(
    credentials_path: str,
    last_check_timestamp: str,      # ISO format datetime string
    user_profile: dict,
    tax_rules: dict,
    claude_client
) -> list[dict]:
    """
    Scan Gmail for emails with PDF/image attachments since last_check_timestamp.
    
    Logic:
        1. Connect via simplegmail using credentials_path
        2. Search: f"after:{last_check_timestamp} has:attachment"
        3. For each email with attachment:
           a. Filter attachments: only PDF, JPG, PNG, HEIC, JPEG
           b. Download attachment bytes
           c. Call process_document() from invoice_parser
           d. Add "origen": "gmail", "email_subject": subject, "email_date": date
        4. Return list of processed document dicts (same format as process_document return)
    
    Error handling:
        - If Gmail auth fails: return [] and log warning (don't crash app)
        - If individual attachment parse fails: skip it and continue
    
    Note: For demo/prototype, provide get_mock_invoices() that returns
          2-3 hardcoded realistic Spanish invoice dicts for demo purposes.
          Use when GMAIL_DEMO_MODE=true in .env
    """
```

### 5.5 `engine/calendly_client.py`

```python
import requests

CALENDLY_BASE = "https://api.calendly.com"

def get_user_uri(token: str) -> str:
    """GET /users/me → return user URI string"""

def get_scheduled_events(token: str, user_uri: str, min_start_time: str = None) -> list[dict]:
    """
    GET /scheduled_events with user=user_uri, status=active|canceled|completed
    Returns list of normalized event dicts:
    {
        "event_uuid": str,
        "nombre_evento": str,        # event type name
        "cliente_nombre": str,       # invitee name
        "cliente_email": str,        # invitee email
        "fecha_inicio": str,         # ISO datetime
        "fecha_fin": str,
        "estado": str,               # "activo" | "completado" | "cancelado"
        "precio": float | None,      # from event type if set
    }
    
    Note: Calendly free plan may not expose pricing. Use None and let user fill in.
    For demo: provide get_mock_events() returning 3-4 hardcoded events.
    Use when CALENDLY_DEMO_MODE=true in .env
    """

def generate_invoice_draft(event: dict, user_profile: dict) -> dict:
    """
    Convert a Calendly event into a ledger-ready ingreso draft.
    Returns dict with ledger schema fields pre-filled.
    tipo_iva defaults to 21 (professional services).
    estado defaults to "pendiente".
    origen = "calendly"
    User still confirms before saving.
    """
```

---

## 6. Streamlit Pages — Widget-by-Widget Spec

### 6.1 `app.py` — Entry Point

```python
import streamlit as st
import json
from pathlib import Path

st.set_page_config(
    page_title="Alta Fácil Pro",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Session state init — run before anything else
def init_session_state():
    defaults = {
        "messages": [],                    # Chatbot history
        "last_gmail_check": None,          # ISO datetime string
        "gmail_connected": False,
        "calendly_connected": False,
        "calendly_token": None,
        "processed_document": None,        # Last scanner result
        "ledger_cache_key": 0,            # Increment to force reload
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session_state()

# Route to onboarding if first run
profile_path = Path("data/user_profile.json")
if not profile_path.exists():
    st.switch_page("pages/0_Onboarding.py")
else:
    with open(profile_path) as f:
        profile = json.load(f)
    if not profile.get("onboarding_complete"):
        st.switch_page("pages/0_Onboarding.py")
    else:
        st.session_state["user_profile"] = profile
        st.switch_page("pages/1_Dashboard.py")
```

### 6.2 `pages/0_Onboarding.py`

**Widget sequence (all inside a single `st.form("onboarding_form")`):**

```python
st.title("🚀 Bienvenido a Alta Fácil Pro")
st.subheader("Cuéntanos sobre ti para personalizar tu experiencia")

# Inside st.form("onboarding_form"):
nombre = st.text_input("Tu nombre", placeholder="María García")

actividad = st.text_input(
    "¿A qué te dedicas?",
    placeholder="Consultoría de marketing digital, diseño web, fisioterapia..."
)

iva_regime = st.radio(
    "Régimen de IVA",
    options=["Régimen General", "Régimen Simplificado", "Exento de IVA"],
    index=0,
    help="La mayoría de autónomos de servicios están en Régimen General"
)

work_location = st.radio(
    "¿Dónde trabajas habitualmente?",
    options=["En casa (home office)", "En oficina/coworking", "Mixto"],
    horizontal=True    # NEW WIDGET — not used in class
)

# Show this only if work_location is casa or mixto
if work_location != "En oficina/coworking":
    home_office_pct = st.slider(
        "% de tu vivienda que usas para trabajar",
        min_value=5, max_value=50, value=30, step=5,
        help="Típicamente entre el 20% y el 30% para un despacho en casa"
    )

tarifa_plana = st.checkbox(
    "Soy nuevo autónomo y tengo (o voy a pedir) la Tarifa Plana",
    value=True
)

alta_date = st.date_input(
    "Fecha de alta como autónomo (o fecha prevista)",
    help="Usaremos esto para calcular tu periodo de Tarifa Plana"
)

irpf_retencion = st.select_slider(
    "Retención IRPF en tus facturas",
    options=[0, 7, 15, 19],
    value=15,
    help="Nuevos autónomos: 7% los 3 primeros años. El estándar es 15%."
)

submitted = st.form_submit_button("Empezar mi Alta Fácil Pro →", type="primary")
```

**On submit:** validate (nombre and actividad must not be empty), save to `data/user_profile.json`, `st.switch_page("pages/1_Dashboard.py")`.

### 6.3 `pages/1_Dashboard.py`

```python
# Load data
@st.cache_data(ttl=30)
def cached_ledger():
    return load_ledger()

df = cached_ledger()
quarter = get_current_quarter()
summary = get_quarterly_summary(df, quarter)
monthly = get_monthly_breakdown(df, datetime.now().year)

# Title row
st.title(f"Buenos días, {profile['nombre'].split()[0]} 👋")
st.caption(f"Resumen de {quarter} — actualizado hace menos de 30 segundos")

# KPI row — 4 metrics
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(
        label="💶 Facturado este trimestre",
        value=f"€{summary['total_ingresos']:,.0f}",
        delta=f"vs Q anterior: +€{delta_ingresos:,.0f}"  # compare to last quarter
    )
with col2:
    st.metric(
        label="🧾 Gastos deducibles",
        value=f"€{summary['total_gastos_deducibles']:,.0f}",
        delta=None
    )
with col3:
    # Color warning if IVA > €1000
    st.metric(
        label="🏛️ IVA a liquidar (aprox.)",
        value=f"€{max(0, summary['resultado_303']):,.0f}",
        delta="Modelo 303",
        delta_color="off"
    )
with col4:
    st.metric(
        label="💰 Provisión IRPF",
        value=f"€{summary['irpf_provision']:,.0f}",
        delta="Reserva esto cada mes",
        delta_color="off"
    )

# Cashflow chart — Plotly
import plotly.graph_objects as go
fig = go.Figure()
fig.add_bar(name="Ingresos", x=monthly["month"], y=monthly["ingresos"], marker_color="#00D9A5")
fig.add_bar(name="Gastos", x=monthly["month"], y=monthly["gastos_base"], marker_color="#E94560")
fig.add_bar(name="Provisión impuestos", x=monthly["month"], y=monthly["tax_provision"], marker_color="#FFC93C")
fig.update_layout(
    barmode="group",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#EDF2F4",
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    height=350
)
st.plotly_chart(fig, use_container_width=True)

# Recent transactions
st.subheader("Últimos movimientos")
recent = df.tail(10).sort_values("fecha", ascending=False)

def color_row(row):
    if row["tipo"] == "ingreso":
        return ["background-color: rgba(0,217,165,0.1)"] * len(row)
    elif row["deducible"]:
        return ["background-color: rgba(233,69,96,0.1)"] * len(row)
    else:
        return ["background-color: rgba(255,201,60,0.1)"] * len(row)

styled = recent[["fecha","tipo","proveedor_cliente","concepto","total","deducible","estado"]].style.apply(color_row, axis=1)
st.dataframe(styled, use_container_width=True, hide_index=True)

# Gmail toast notifications
if st.session_state.get("gmail_connected") and should_poll_gmail():
    new_invoices = check_new_invoices(...)
    for inv in new_invoices:
        st.toast(f"📧 Nueva factura detectada: {inv['proveedor']} — €{inv['total']:.2f}", icon="📧")
        save_to_ledger(inv)
```

### 6.4 `pages/2_Scanner.py` — THE CORE SCREEN

```python
st.title("🔍 Escáner de Facturas")
st.caption("Sube, fotografía o introduce tu factura. La IA clasifica automáticamente.")

# Method selector — st.radio horizontal (NEW WIDGET)
method = st.radio(
    "¿Cómo quieres añadir tu factura?",
    options=["📁 Subir archivo", "📷 Hacer foto", "✍️ Introducir manualmente"],
    horizontal=True,      # THIS IS THE NEW WIDGET — horizontal radio
    label_visibility="collapsed"
)

uploaded_file = None
camera_image = None

if method == "📁 Subir archivo":
    uploaded_file = st.file_uploader(
        "Arrastra tu factura aquí",
        type=["pdf", "jpg", "jpeg", "png", "heic"],
        label_visibility="collapsed"
    )
    if uploaded_file:
        if uploaded_file.type.startswith("image"):
            st.image(uploaded_file, caption="Vista previa", width=400)

elif method == "📷 Hacer foto":
    camera_image = st.camera_input(    # NEW WIDGET — camera_input
        "Apunta la cámara a tu factura o recibo"
    )

elif method == "✍️ Introducir manualmente":
    with st.form("manual_entry"):
        col1, col2 = st.columns(2)
        with col1:
            m_proveedor = st.text_input("Proveedor *")
            m_fecha = st.date_input("Fecha factura")
            m_concepto = st.text_input("Concepto *", placeholder="Hosting web, Formación Python...")
            m_numero = st.text_input("Nº Factura")
        with col2:
            m_base = st.number_input("Base imponible (€) *", min_value=0.01, step=0.01)
            m_tipo_iva = st.selectbox("Tipo IVA", options=[21, 10, 4, 0], index=0)
            m_cuota = m_base * m_tipo_iva / 100
            st.metric("Cuota IVA calculada", f"€{m_cuota:.2f}")
            m_total = m_base + m_cuota
            st.metric("Total factura", f"€{m_total:.2f}")
        submit_manual = st.form_submit_button("Clasificar con IA →", type="primary")

# Process button — only show if file/image is ready
file_ready = uploaded_file is not None or camera_image is not None
if file_ready:
    if st.button("🔍 Analizar con IA", type="primary", use_container_width=True):
        with st.spinner("Procesando con OCR y Claude... (5-10 segundos)"):
            file_bytes = uploaded_file.read() if uploaded_file else camera_image.getvalue()
            file_type = "pdf" if (uploaded_file and uploaded_file.type == "application/pdf") else "image"
            result = process_document(file_bytes, file_type, profile, tax_rules, claude_client)
            st.session_state["processed_document"] = result

# Results display — show if we have a result
if st.session_state.get("processed_document"):
    result = st.session_state["processed_document"]
    
    st.divider()
    st.subheader("Resultado del análisis")
    
    # Three columns: extraction | verdict | edit
    col_extract, col_verdict, col_edit = st.columns([1, 1, 1])
    
    with col_extract:
        st.subheader("📄 Datos extraídos")
        st.metric("Proveedor", result["proveedor"])        # st.metric — NEW WIDGET
        st.metric("Fecha", result["fecha"])
        st.metric("Base imponible", f"€{result['base_imponible']:.2f}")
        st.metric("IVA", f"{result['tipo_iva']}% → €{result['cuota_iva']:.2f}")
        st.metric("Total", f"€{result['total']:.2f}")
    
    with col_verdict:
        st.subheader("⚖️ Clasificación fiscal")
        
        # IVA rate verdict
        st.info(f"**IVA: {result['tipo_iva']}% ({result['iva_label']})**\n\n{result['iva_article']}")
        
        # Deductibility verdict
        pct = result["porcentaje_deduccion"]
        if pct == 100:
            st.success(f"✅ **100% deducible**\n\n€{result['cuota_iva_deducible']:.2f} deducible\n\n_{result['deductibility_article']}_")
        elif pct > 0:
            st.warning(f"⚠️ **{pct}% deducible**\n\n€{result['cuota_iva_deducible']:.2f} de €{result['cuota_iva']:.2f}\n\n_{result['deductibility_article']}_")
        else:
            st.error(f"❌ **No deducible**\n\n_{result['deductibility_article']}_")
        
        st.caption("_Orientativo. Consulta siempre con tu gestor para declaraciones oficiales._")
    
    with col_edit:
        st.subheader("✏️ Corregir si es necesario")
        with st.expander("Editar extracción", expanded=False):
            r_proveedor = st.text_input("Proveedor", value=result["proveedor"], key="r_prov")
            r_fecha = st.text_input("Fecha (YYYY-MM-DD)", value=result["fecha"], key="r_fecha")
            r_base = st.number_input("Base imponible", value=result["base_imponible"], key="r_base")
            r_iva = st.selectbox("Tipo IVA", [21, 10, 4, 0], index=[21,10,4,0].index(result["tipo_iva"]), key="r_iva")
            r_concepto = st.text_input("Concepto", value=result["concepto"], key="r_conc")
            if st.button("Aplicar correcciones"):
                # Update result in session state and re-run classify_iva/classify_deductibility
                pass
    
    # Save button
    st.divider()
    if st.button("💾 Guardar en mi libro de cuentas", type="primary", use_container_width=True):
        entry = build_ledger_entry_from_result(result, origen="scanner")
        save_to_ledger(entry)
        st.balloons()
        st.success(f"✅ Factura de {result['proveedor']} guardada. IVA deducible registrado: €{result['cuota_iva_deducible']:.2f}")
        st.session_state["processed_document"] = None

# Recent entries at bottom
st.divider()
st.subheader("Últimas facturas registradas")
df = load_ledger()
gastos = df[df["tipo"] == "gasto"].tail(10).sort_values("fecha", ascending=False)
# Color code by deductibility
def color_deducible(val):
    if val == True: return "background-color: rgba(0,217,165,0.15)"
    return "background-color: rgba(233,69,96,0.15)"
styled = gastos[["fecha","proveedor_cliente","concepto","total","tipo_iva","porcentaje_deduccion","cuota_iva_deducible"]].style.applymap(color_deducible, subset=["deducible"])
st.dataframe(styled, use_container_width=True, hide_index=True)
```

### 6.5 `pages/3_AR_Agenda.py`

```python
st.title("📅 Mi Agenda y Facturación")

tab_upcoming, tab_invoices, tab_aging = st.tabs(["Próximas Citas", "Facturas Emitidas", "AR Aging"])

with tab_upcoming:
    if not st.session_state.get("calendly_connected"):
        st.info("Conecta Calendly en el sidebar para ver tus citas automáticamente.")
        st.caption("Sin Calendly, puedes añadir ingresos manualmente desde el escáner.")
    else:
        events = get_scheduled_events(token, user_uri)
        df_events = pd.DataFrame(events)
        st.dataframe(df_events, use_container_width=True, hide_index=True)
        
        # For each completed event, show "Generar Factura" button
        completed = [e for e in events if e["estado"] == "completado"]
        for ev in completed:
            col_info, col_btn = st.columns([3, 1])
            with col_info:
                st.write(f"**{ev['nombre_evento']}** con {ev['cliente_nombre']} — {ev['fecha_inicio'][:10]}")
            with col_btn:
                if st.button("🧾 Generar factura", key=f"inv_{ev['event_uuid']}"):
                    draft = generate_invoice_draft(ev, profile)
                    st.session_state["invoice_draft"] = draft
                    st.switch_page("pages/2_Scanner.py")

with tab_invoices:
    df = load_ledger()
    ingresos = df[df["tipo"] == "ingreso"].sort_values("fecha", ascending=False)
    st.metric("Total facturado", f"€{ingresos['total'].sum():,.2f}")
    st.metric("Pendiente de cobro", f"€{ingresos[ingresos['estado']=='pendiente']['total'].sum():,.2f}")
    st.dataframe(ingresos[["fecha","proveedor_cliente","concepto","total","estado"]], use_container_width=True, hide_index=True)

with tab_aging:
    st.subheader("Facturas pendientes de cobro")
    aging_df = get_ar_aging(load_ledger())
    
    # Color by aging bucket
    def color_aging(val):
        colors = {"0-30": "#00D9A5", "31-60": "#FFC93C", "61-90": "#FF8C00", "90+": "#E94560"}
        return f"color: {colors.get(val, 'white')}"
    
    styled = aging_df.style.applymap(color_aging, subset=["aging_bucket"])
    st.dataframe(styled, use_container_width=True, hide_index=True)
```

### 6.6 `pages/4_FPA.py`

```python
st.title("📊 Mi Trimestre — FP&A")
st.caption("Proyección fiscal en tiempo real basada en tus datos reales")

# Quarter selector in sidebar
quarter = st.sidebar.selectbox(
    "Trimestre",
    options=["2025-Q1", "2025-Q2", "2025-Q3", "2025-Q4"],
    index=get_current_quarter_index()
)

df = load_ledger()
summary = get_quarterly_summary(df, quarter)
ytd = get_ytd_summary(df, 2025, int(quarter[-1]))

# WHAT-IF SLIDERS — these must recalculate everything in real time
st.subheader("🎛️ Simulador 'Y si...'")
col_s1, col_s2 = st.columns(2)
with col_s1:
    extra_ingresos = st.slider(
        "Ingresos adicionales esperados este trimestre (€)",
        min_value=0, max_value=20000, value=0, step=500,
        help="¿Tienes proyectos en pipeline? Añádelos para ver el impacto"
    )
with col_s2:
    extra_gastos = st.slider(
        "Gastos deducibles pendientes de este trimestre (€)",
        min_value=0, max_value=10000, value=0, step=100,
        help="Facturas de gastos aún no escaneadas que sabes que tienes"
    )

# Recalculate with slider values
adj_summary = {
    **summary,
    "total_ingresos": summary["total_ingresos"] + extra_ingresos,
    "total_gastos_deducibles": summary["total_gastos_deducibles"] + extra_gastos,
    "iva_cobrado": summary["iva_cobrado"] + (extra_ingresos * 0.21),
    "iva_soportado_deducible": summary["iva_soportado_deducible"] + (extra_gastos * 0.21),
}
adj_summary["resultado_303"] = adj_summary["iva_cobrado"] - adj_summary["iva_soportado_deducible"]
adj_summary["beneficio_neto"] = adj_summary["total_ingresos"] - adj_summary["total_gastos_deducibles"]
adj_summary["irpf_provision"] = adj_summary["beneficio_neto"] * 0.20

# Modelo 303 expander
with st.expander("🏛️ Modelo 303 — Liquidación IVA", expanded=True):
    col1, col2, col3 = st.columns(3)
    col1.metric("IVA Cobrado (repercutido)", f"€{adj_summary['iva_cobrado']:,.2f}")
    col2.metric("IVA Pagado deducible (soportado)", f"€{adj_summary['iva_soportado_deducible']:,.2f}")
    resultado = adj_summary["resultado_303"]
    if resultado >= 0:
        col3.metric("🔴 A pagar a Hacienda", f"€{resultado:,.2f}")
    else:
        col3.metric("🟢 A compensar próximo trimestre", f"€{abs(resultado):,.2f}")

# Modelo 130 expander
with st.expander("💰 Modelo 130 — Pago Fraccionado IRPF", expanded=True):
    m130 = calculate_modelo_130(df[df["trimestre"].str.startswith("2025")], retenciones_ytd=0)
    col1, col2, col3 = st.columns(3)
    col1.metric("Ingresos YTD", f"€{m130['ingresos_ytd']:,.2f}")
    col2.metric("Gastos deducibles YTD", f"€{m130['gastos_deducibles_ytd']:,.2f}")
    col3.metric("Pago fraccionado (20%)", f"€{m130['pago_neto']:,.2f}")

# Cashflow projection
with st.expander("📈 Cashflow proyectado", expanded=False):
    st.info(f"""
    **Resumen del trimestre:**  
    Ingresos: €{adj_summary['total_ingresos']:,.2f}  
    Gastos deducibles: €{adj_summary['total_gastos_deducibles']:,.2f}  
    **Beneficio neto estimado: €{adj_summary['beneficio_neto']:,.2f}**  
    
    Reserva sugerida para impuestos: €{(adj_summary['irpf_provision'] + max(0, resultado)):,.2f}
    """)

# Deadline countdown
st.subheader("⏰ Próximos plazos")
deadline_info = get_next_deadline(quarter)   # Returns (modelo, deadline_date, days_remaining)
days = deadline_info["days_remaining"]
progress_val = max(0, min(1, 1 - days/90))
color = "normal" if days > 30 else ("off" if days > 15 else "inverse")
st.metric(f"Modelo {deadline_info['modelo']} — {deadline_info['deadline_date']}", f"{days} días restantes", delta_color=color)
st.progress(progress_val)
```

### 6.7 `pages/5_Chatbot.py`

```python
import anthropic
import streamlit as st

st.title("🤖 El Gestor — Tu Asesor Fiscal IA")
st.info("El Gestor te orienta basándose en tus datos reales. No reemplaza a un gestor para declaraciones oficiales.")

# Build dynamic system prompt from live data
def build_system_prompt(profile: dict, summary: dict) -> str:
    return f"""Eres El Gestor, un asesor fiscal especializado en autónomos españoles. 
Tienes acceso a los datos financieros reales del usuario para este trimestre.

PERFIL DEL USUARIO:
{json.dumps(profile, ensure_ascii=False, indent=2)}

RESUMEN FINANCIERO TRIMESTRE ACTUAL ({get_current_quarter()}):
- Ingresos totales: €{summary['total_ingresos']:,.2f}
- Gastos deducibles: €{summary['total_gastos_deducibles']:,.2f}
- IVA cobrado (repercutido): €{summary['iva_cobrado']:,.2f}
- IVA soportado deducible: €{summary['iva_soportado_deducible']:,.2f}
- Resultado Modelo 303: €{summary['resultado_303']:,.2f} ({'a pagar' if summary['resultado_303'] > 0 else 'a compensar'})
- Beneficio neto estimado: €{summary['beneficio_neto']:,.2f}
- Provisión IRPF estimada: €{summary['irpf_provision']:,.2f}

INSTRUCCIONES:
- Responde SIEMPRE en español, de forma clara y sin jerga técnica innecesaria
- Cuando cites artículos legales, menciona la ley completa (e.g. "Art. 90.Uno Ley 37/1992")
- Usa los datos reales del usuario para respuestas personalizadas
- SIEMPRE añade al final: "Para declaraciones oficiales, consulta siempre con tu gestor"
- Si no sabes algo con certeza, dilo claramente
- Sé conciso — máximo 3-4 párrafos por respuesta"""

# Load summary for system prompt
df = load_ledger()
summary = get_quarterly_summary(df, get_current_quarter())
system_prompt = build_system_prompt(profile, summary)

# Display chat history
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):       # st.chat_message — NEW WIDGET
        st.markdown(msg["content"])

# Suggested questions (only if no messages yet)
if not st.session_state["messages"]:
    st.caption("💬 Prueba a preguntar:")
    col1, col2, col3 = st.columns(3)
    suggestions = [
        "¿Cuánto debo para el 303 este trimestre?",
        "¿Puedo deducir mi portátil nuevo?",
        "¿Qué pasa si facturo €3.000 más este mes?"
    ]
    for i, (col, q) in enumerate(zip([col1, col2, col3], suggestions)):
        with col:
            if st.button(q, key=f"sugg_{i}", use_container_width=True):
                st.session_state["messages"].append({"role": "user", "content": q})
                st.rerun()

# Chat input — NEW WIDGET
if prompt := st.chat_input("Pregunta a El Gestor..."):     # st.chat_input — NEW WIDGET
    st.session_state["messages"].append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        
        # Stream the response
        with st.spinner("El Gestor está pensando..."):
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1000,
                system=system_prompt,
                messages=[
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state["messages"]
                ]
            )
            reply = response.content[0].text
        
        st.markdown(reply)
        st.session_state["messages"].append({"role": "assistant", "content": reply})
```

---

## 7. Shared Sidebar

Add this to every page file (or extract to a `shared/sidebar.py` and call it):

```python
def render_sidebar(profile: dict, summary: dict):
    with st.sidebar:
        # User greeting
        st.markdown(f"### 🚀 {profile['nombre']}")
        st.caption(f"Autónomo desde {profile['alta_date']}")
        st.divider()
        
        # Quick KPIs
        st.metric("Facturado este Q", f"€{summary['total_ingresos']:,.0f}")
        st.metric("IVA a liquidar", f"€{max(0, summary['resultado_303']):,.0f}")
        st.divider()
        
        # Gmail connection
        if not st.session_state.get("gmail_connected"):
            if st.button("📧 Conectar Gmail", use_container_width=True):
                # Trigger OAuth flow
                st.session_state["gmail_connected"] = False  # Set True after OAuth
                st.info("Funcionalidad OAuth — configura credentials.json primero")
        else:
            st.success("📧 Gmail conectado")
        
        # Calendly connection  
        if not st.session_state.get("calendly_connected"):
            token = st.text_input("🗓️ Calendly API Token", type="password", key="calendly_input")
            if token and st.button("Conectar Calendly", use_container_width=True):
                st.session_state["calendly_token"] = token
                st.session_state["calendly_connected"] = True
                st.rerun()
        else:
            st.success("🗓️ Calendly conectado")
        
        st.divider()
        st.caption("Alta Fácil Pro — PDAI 2026")
```

---

## 8. Streamlit Configuration

**`.streamlit/config.toml`** — exact values, copy verbatim:

```toml
[theme]
primaryColor = "#E94560"
backgroundColor = "#1A1A2E"
secondaryBackgroundColor = "#16213E"
textColor = "#EDF2F4"
font = "sans serif"

[server]
maxUploadSize = 50
enableCORS = false

[browser]
gatherUsageStats = false
```

---

## 9. Environment Variables

**`.env`** (never commit):
```
ANTHROPIC_API_KEY=sk-ant-...
CALENDLY_DEMO_MODE=true          # Set false to use real Calendly API
CALENDLY_ACCESS_TOKEN=           # Required if CALENDLY_DEMO_MODE=false
GMAIL_DEMO_MODE=true             # Set false to use real Gmail OAuth
GMAIL_CREDENTIALS_PATH=credentials.json   # Required if GMAIL_DEMO_MODE=false
```

**`.env.example`** (commit this):
```
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
CALENDLY_DEMO_MODE=true
CALENDLY_ACCESS_TOKEN=
GMAIL_DEMO_MODE=true
GMAIL_CREDENTIALS_PATH=credentials.json
```

---

## 10. Dependencies

**`requirements.txt`**:
```
# Frontend
streamlit>=1.35.0
plotly>=5.18.0
pandas>=2.0.0
python-dotenv>=1.0.0

# AI & Document Intelligence
anthropic>=0.25.0
pillow>=10.0.0
pytesseract>=0.3.10
opencv-python>=4.9.0.80
pdfplumber>=0.10.0
pdf2image>=1.16.3

# External Integrations
simplegmail>=4.2.0
google-auth-oauthlib>=1.2.0
google-api-python-client>=2.120.0
requests>=2.31.0

# Utilities
python-dateutil>=2.8.0
pytz>=2024.1
```

**System dependencies (install before pip):**
```bash
# macOS
brew install tesseract tesseract-lang poppler

# Ubuntu/Debian
sudo apt install tesseract-ocr tesseract-ocr-spa poppler-utils
```

---

## 11. Code Patterns & Constraints

### 11.1 Caching Pattern
```python
# Always cache expensive calls — ledger, tax rules
@st.cache_data(ttl=30)          # 30s TTL for ledger (changes frequently)
def get_cached_ledger():
    return load_ledger()

@st.cache_data                   # No TTL for tax rules (static file)
def get_cached_tax_rules():
    return load_tax_rules()

# ALWAYS invalidate cache after writing to ledger:
def save_to_ledger(entry):
    # ... write to CSV ...
    get_cached_ledger.clear()   # Force reload on next call
```

### 11.2 Session State Pattern
```python
# Initialize ALL session state keys in app.py init_session_state()
# Never access st.session_state[key] without checking existence first
value = st.session_state.get("key", default_value)

# Persist scanner result between reruns (crucial — scanner reruns on every widget change)
st.session_state["processed_document"] = result   # After process_document()
```

### 11.3 Error Handling Pattern
```python
# All AI calls must be wrapped — never crash the UI
try:
    result = process_document(...)
except ValueError as e:
    st.error(f"❌ Error procesando el documento: {e}")
    st.caption("Prueba a mejorar la iluminación o usa la entrada manual.")
    st.stop()
except anthropic.APIError as e:
    st.error(f"❌ Error de API: {e}")
    st.stop()
```

### 11.4 Claude API Pattern
```python
import anthropic
import os

# Initialize client once per page (not per call)
@st.cache_resource
def get_claude_client():
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

client = get_claude_client()

# Invoice extraction → claude-haiku-4-5 (fast, cheap)
# Chatbot → claude-sonnet-4-6 (smarter, handles nuance)
```

### 11.5 Demo Mode Pattern
```python
# All external integrations check demo mode first
import os

GMAIL_DEMO = os.getenv("GMAIL_DEMO_MODE", "true").lower() == "true"
CALENDLY_DEMO = os.getenv("CALENDLY_DEMO_MODE", "true").lower() == "true"

if GMAIL_DEMO:
    invoices = get_mock_gmail_invoices()   # Returns hardcoded list
else:
    invoices = check_new_invoices(...)
```

### 11.6 IVA Calculation Consistency Rule
```python
# ALWAYS calculate cuota_iva from base_imponible — never trust extracted cuota directly
# Claude may extract cuota incorrectly; recalculate and surface discrepancy to user
extracted_cuota = result.get("cuota_iva", 0)
calculated_cuota = round(result["base_imponible"] * result["tipo_iva"] / 100, 2)

if abs(extracted_cuota - calculated_cuota) > 0.05:
    st.warning(f"⚠️ Discrepancia en IVA: factura dice €{extracted_cuota:.2f}, calculado €{calculated_cuota:.2f}. Verifica la factura.")
    result["cuota_iva"] = calculated_cuota  # Use calculated value
```

### 11.7 Disclaimer Rule
Every tax classification shown to the user MUST use the translated disclaimer via `t()`:
```python
# In every page, after a tax verdict:
st.caption(t("disclaimer_tax"))
# es.json: "Orientativo. Consulta siempre con tu gestor para declaraciones oficiales."
# en.json: "Indicative only. Always consult your accountant for official filings."
```

### 11.8 New Widgets Checklist (Assignment Requirement)
The following widgets MUST appear and be functional in the final app — they are "not used in class" and satisfy the assignment requirement:

| Widget | Location | Purpose |
|---|---|---|
| `st.camera_input()` | `2_Scanner.py` | Live photo of receipt |
| `st.radio(horizontal=True)` | `2_Scanner.py` | Upload method selector |
| `st.chat_message()` | `5_Chatbot.py` | Chat bubble display |
| `st.chat_input()` | `5_Chatbot.py` | Chat text input |
| `st.metric()` with delta | `1_Dashboard.py` | KPI cards |
| `st.toast()` | `1_Dashboard.py` | Gmail invoice notification |
| `st.select_slider()` | `0_Onboarding.py` | IRPF retention selector |


---

## 12. Internationalisation (i18n) — Bilingual ES/EN

> **Rule:** Every user-facing string in every page MUST come from `t("key")`. No hardcoded Spanish or English strings in page files or engine files. Zero exceptions.

### 12.1 Architecture

**Pattern: JSON string files + `t()` helper function.**

- `i18n/es.json` — Spanish (canonical, source of truth)
- `i18n/en.json` — English (full translation, same keys)
- `i18n/__init__.py` — exports `t(key)`, `get_lang()`, `set_lang(lang)`
- Language stored in `st.session_state["lang"]` — default `"es"`
- Switching language triggers `st.rerun()` — instant, no page reload

### 12.2 `i18n/__init__.py` — Full Implementation

```python
import json
import streamlit as st
from pathlib import Path

LANGS = ["es", "en"]
LANG_LABELS = {"es": "🇪🇸 Español", "en": "🇬🇧 English"}
DEFAULT_LANG = "es"

_cache: dict[str, dict] = {}

def _load(lang: str) -> dict:
    if lang not in _cache:
        path = Path(__file__).parent / f"{lang}.json"
        with open(path, encoding="utf-8") as f:
            _cache[lang] = json.load(f)
    return _cache[lang]

def get_lang() -> str:
    return st.session_state.get("lang", DEFAULT_LANG)

def set_lang(lang: str) -> None:
    assert lang in LANGS, f"Unsupported language: {lang}"
    st.session_state["lang"] = lang

def t(key: str, **kwargs) -> str:
    """
    Translate a key to the current language.
    
    Args:
        key: Dot-notation key, e.g. "dashboard.title", "scanner.btn_analyze"
        **kwargs: Format substitutions, e.g. t("dashboard.greeting", name="María")
    
    Returns:
        Translated string. Falls back to Spanish if key missing in English.
        Falls back to key itself if missing in both (never crashes).
    
    Usage:
        st.title(t("dashboard.title"))
        st.button(t("scanner.btn_save"))
        st.metric(t("dashboard.kpi_revenue"), value=f"€{total:,.0f}")
        st.warning(t("scanner.iva_discrepancy", extracted=2.10, calculated=2.31))
    """
    lang = get_lang()
    strings = _load(lang)
    
    # Support dot-notation: "dashboard.title" → strings["dashboard"]["title"]
    keys = key.split(".")
    val = strings
    for k in keys:
        if isinstance(val, dict) and k in val:
            val = val[k]
        else:
            # Fallback to Spanish
            val = _load("es")
            for k2 in keys:
                if isinstance(val, dict) and k2 in val:
                    val = val[k2]
                else:
                    return key  # Last resort: return key itself
            break
    
    if not isinstance(val, str):
        return key
    
    return val.format(**kwargs) if kwargs else val
```

### 12.3 Language Switcher — Sidebar Implementation

Add this to the `render_sidebar()` function in every page, BEFORE any other sidebar content:

```python
def render_lang_switcher():
    """Must be the FIRST thing rendered in every sidebar."""
    current = get_lang()
    col_es, col_en = st.sidebar.columns(2)
    
    with col_es:
        if st.button(
            "🇪🇸 ES",
            type="primary" if current == "es" else "secondary",
            use_container_width=True,
            key="lang_es"
        ):
            set_lang("es")
            st.rerun()
    
    with col_en:
        if st.button(
            "🇬🇧 EN",
            type="primary" if current == "en" else "secondary",
            use_container_width=True,
            key="lang_en"
        ):
            set_lang("en")
            st.rerun()
    
    st.sidebar.divider()
```

### 12.4 Chatbot Language Injection

The chatbot system prompt must include the active language so Claude responds in the correct language:

```python
def build_system_prompt(profile: dict, summary: dict) -> str:
    lang = get_lang()
    response_language = "Spanish" if lang == "es" else "English"
    
    return f"""You are El Gestor, a tax advisor specialised in Spanish autónomos.
IMPORTANT: Always respond in {response_language}. Never switch languages mid-response.

USER PROFILE:
{json.dumps(profile, ensure_ascii=False, indent=2)}

CURRENT QUARTER FINANCIAL SUMMARY ({get_current_quarter()}):
...
"""
```

### 12.5 Tax Term Convention — Spanish Term + English Tooltip

In English mode, Spanish tax terms are displayed AS-IS (e.g. "Modelo 303") with an English explanation injected as a Streamlit `help=` tooltip. This is the correct UX: the UI stays clean, the user learns the Spanish term they will encounter on real AEAT forms, and the tooltip provides instant clarification on hover.

**Implementation pattern:**
```python
# Use t() for the label, t() for the tooltip help text — separately keyed
st.metric(
    label=t("tax_terms.modelo_303"),           # ES: "Modelo 303"  EN: "Modelo 303"
    value=f"€{a_pagar:,.2f}",
    help=t("tax_terms.modelo_303_tooltip")     # ES: None  EN: "Quarterly VAT return filed every 3 months"
)

# For section headers, use st.subheader + st.caption pattern:
st.subheader(t("fpa.m303_title"))              # ES: "Modelo 303"  EN: "Modelo 303"
st.caption(t("fpa.m303_tooltip"))              # ES: ""  EN: "Quarterly VAT Return — filed in April, July, October, January"

# For table column headers and dataframe labels: use help= on the parent widget
st.dataframe(df, help=t("scanner.table_tooltip"))
```

**All Spanish tax terms and their English tooltips:**

| Spanish term | `tax_terms.X` key | English tooltip (`tax_terms.X_tooltip`) |
|---|---|---|
| Modelo 303 | `modelo_303` | "Quarterly VAT return. Filed in April, July, October and January." |
| Modelo 130 | `modelo_130` | "Quarterly income tax prepayment. 20% of net profit, filed same dates as Modelo 303." |
| Cuota SS | `cuota_ss` | "Monthly Social Security contribution paid to Seguridad Social (RETA system)." |
| IVA repercutido | `iva_repercutido` | "Output VAT — the VAT you charge clients on your invoices." |
| IVA soportado | `iva_soportado` | "Input VAT — the VAT you pay on your business expenses." |
| Base imponible | `base_imponible` | "Net amount before VAT is added." |
| Autónomo | `autonomo` | "Self-employed / freelancer status in Spain. Requires registration with Hacienda and Seguridad Social." |
| Hacienda | `hacienda` | "The Spanish Tax Agency (Agencia Tributaria / AEAT). Manages VAT and income tax." |
| Gestor | `gestor` | "A Spanish accountant/tax advisor. Recommended for official tax filings." |
| Tarifa Plana | `tarifa_plana` | "Flat-rate Social Security scheme for new freelancers: €80/month for the first 12 months." |
| IRPF | `irpf` | "Personal income tax (Impuesto sobre la Renta de las Personas Físicas). Withheld at 15% on most professional invoices." |
| Estimación Directa | `estimacion_directa` | "Standard income tax calculation method: actual income minus actual deductible expenses." |

**In es.json, all tooltip keys are empty strings** — Spanish users do not need tooltips for their own tax terms:
```json
// es.json — tooltips empty in Spanish
{
  "tax_terms": {
    "modelo_303": "Modelo 303",
    "modelo_303_tooltip": "",
    "modelo_130": "Modelo 130",
    "modelo_130_tooltip": ""
  }
}
```

**In en.json, tooltips are full English explanations:**
```json
// en.json — tooltips populated in English
{
  "tax_terms": {
    "modelo_303": "Modelo 303",
    "modelo_303_tooltip": "Quarterly VAT return. Filed in April, July, October and January.",
    "modelo_130": "Modelo 130",
    "modelo_130_tooltip": "Quarterly income tax prepayment. 20% of net profit, filed same dates as Modelo 303."
  }
}
```

**Rendering helper for tax terms with conditional tooltip:**
```python
def tax_term(key: str, **metric_kwargs):
    """
    Render a tax term label. In English, adds tooltip automatically.
    Use instead of t() when the string is a Spanish tax term.
    
    Usage:
        # As metric label:
        st.metric(label=tax_label("modelo_303"), value="€450")
        
        # As subheader with caption tooltip:
        tax_header("modelo_303")
    """
    label = t(f"tax_terms.{key}")
    tooltip = t(f"tax_terms.{key}_tooltip")
    return label, tooltip or None

def tax_header(key: str):
    """Render subheader for a tax term, with caption tooltip in English."""
    label, tooltip = tax_term(key)
    st.subheader(label)
    if tooltip:
        st.caption(f"ℹ️ {tooltip}")
```

Export `tax_term`, `tax_header`, and `LANG_LABELS` from `i18n/__init__.py` alongside `t()`.

**Complete export list for `i18n/__init__.py`:**
```python
__all__ = ["t", "get_lang", "set_lang", "LANGS", "LANG_LABELS", "DEFAULT_LANG", "tax_term", "tax_header"]
```

### 12.6 Claude Invoice Extraction — Language Handling

The OCR + Claude extraction pipeline (`engine/invoice_parser.py`) always extracts in the **document's own language** (Spanish for Spanish invoices, regardless of UI language). The extracted field values (proveedor, concepto, etc.) are raw data — they are stored in the ledger as-is and never translated.

What IS translated in the scanner UI:
- All labels, buttons, verdicts, and status messages → via `t()`
- Tax classification justifications → the `justification` and `article` fields returned by `classify_deductibility()` and `classify_iva()` must be generated in the active language

**Tax rule justification translation:**

`classify_iva()` and `classify_deductibility()` in `engine/tax_rules.py` accept a `lang` parameter and return justification strings from the JSON string files, not hardcoded:

```python
def classify_iva(concepto: str, proveedor: str, rules: dict, lang: str = "es") -> dict:
    # ... matching logic ...
    return {
        "tipo_iva": 21,
        "label": t("tax_terms.tipo_general"),          # Uses active lang via t()
        "article": "Art. 90.Uno Ley 37/1992",          # Always Spanish — it's a legal citation
        "justification": t("tax_verdicts.general_21", lang=lang),  # Translated explanation
        ...
    }
```

Add a `"tax_verdicts"` key to both JSON files:
```json
// es.json
{
  "tax_verdicts": {
    "general_21": "Tipo general 21% — aplicable a todos los servicios y bienes no incluidos en tipos reducidos.",
    "reducido_10": "Tipo reducido 10% — servicios de hostelería, transporte de viajeros, obras en vivienda.",
    "superreducido_4": "Tipo superreducido 4% — alimentos básicos, medicamentos, libros y prensa.",
    "exento": "Operación exenta de IVA según Art. 20 Ley 37/1992. No se puede deducir el IVA soportado.",
    "deducible_100": "100% deducible — gasto directamente vinculado a la actividad profesional.",
    "deducible_50_vehicle": "50% deducible — vehículo. Máximo deducible salvo uso exclusivo profesional acreditado (Art. 95.Tres LIVA).",
    "deducible_30_home": "30% deducible — suministro del hogar. Porcentaje de superficie destinada a trabajo (Art. 30 Ley 35/2006 IRPF).",
    "no_deducible": "No deducible — gasto de carácter personal no vinculado a la actividad económica (Art. 28 Ley 35/2006 IRPF)."
  }
}

// en.json
{
  "tax_verdicts": {
    "general_21": "Standard rate 21% — applies to all services and goods not covered by reduced rates.",
    "reducido_10": "Reduced rate 10% — hospitality services, passenger transport, residential construction works.",
    "superreducido_4": "Super-reduced rate 4% — basic foods, medicines, books and newspapers.",
    "exento": "VAT-exempt transaction under Art. 20 Ley 37/1992. Input VAT cannot be deducted.",
    "deducible_100": "100% deductible — expense directly linked to professional activity.",
    "deducible_50_vehicle": "50% deductible — vehicle. Maximum deductible unless exclusive professional use is proven (Art. 95.Tres LIVA).",
    "deducible_30_home": "30% deductible — home utility. Percentage of floor space used for work (Art. 30 Ley 35/2006 IRPF).",
    "no_deducible": "Not deductible — personal expense not linked to professional activity (Art. 28 Ley 35/2006 IRPF)."
  }
}
```

**Important:** The legal article citations (e.g. `"Art. 90.Uno Ley 37/1992"`) are **never translated** — they are Spanish legal references and must remain in Spanish in both languages. Only the human-readable explanation text around them is translated.

### 12.7 Complete `i18n/es.json`

```json
{
  "app": {
    "name": "Alta Fácil Pro",
    "tagline": "Hazte autónomo sin líos"
  },
  "nav": {
    "onboarding": "Bienvenida",
    "dashboard": "Resumen",
    "scanner": "Escáner",
    "agenda": "Agenda & AR",
    "fpa": "Mi Trimestre",
    "chatbot": "El Gestor IA"
  },
  "sidebar": {
    "greeting": "Hola, {name}",
    "since": "Autónomo desde {date}",
    "kpi_revenue": "Facturado este trimestre",
    "kpi_iva": "IVA a liquidar",
    "connect_gmail": "Conectar Gmail",
    "gmail_connected": "Gmail conectado",
    "connect_calendly": "Conectar Calendly",
    "calendly_connected": "Calendly conectado",
    "calendly_token_placeholder": "Token de acceso Calendly"
  },
  "onboarding": {
    "title": "Bienvenido a Alta Fácil Pro",
    "subtitle": "Cuéntanos sobre ti para personalizar tu experiencia",
    "field_name": "Tu nombre",
    "field_name_placeholder": "María García",
    "field_actividad": "¿A qué te dedicas?",
    "field_actividad_placeholder": "Consultoría de marketing digital, diseño web...",
    "field_iva_regime": "Régimen de IVA",
    "iva_general": "Régimen General",
    "iva_simplificado": "Régimen Simplificado",
    "iva_exento": "Exento de IVA",
    "field_work_location": "¿Dónde trabajas habitualmente?",
    "location_casa": "En casa (home office)",
    "location_oficina": "En oficina/coworking",
    "location_mixto": "Mixto",
    "field_home_pct": "% de tu vivienda que usas para trabajar",
    "field_home_pct_help": "Típicamente entre el 20% y el 30% para un despacho en casa",
    "field_tarifa_plana": "Soy nuevo autónomo y tengo (o voy a pedir) la Tarifa Plana",
    "field_alta_date": "Fecha de alta como autónomo (o fecha prevista)",
    "field_irpf": "Retención IRPF en tus facturas",
    "field_irpf_help": "Nuevos autónomos: 7% los 3 primeros años. El estándar es 15%.",
    "btn_submit": "Empezar mi Alta Fácil Pro →",
    "error_name_required": "El nombre es obligatorio",
    "error_actividad_required": "La actividad es obligatoria"
  },
  "dashboard": {
    "title": "Buenos días, {name}",
    "subtitle": "Resumen de {quarter} — actualizado hace menos de 30 segundos",
    "kpi_revenue_label": "Facturado este trimestre",
    "kpi_expenses_label": "Gastos deducibles",
    "kpi_iva_label": "IVA a liquidar (aprox.)",
    "kpi_irpf_label": "Provisión IRPF",
    "kpi_irpf_delta": "Reserva esto cada mes",
    "chart_title": "Cashflow mensual",
    "chart_ingresos": "Ingresos",
    "chart_gastos": "Gastos",
    "chart_provision": "Provisión impuestos",
    "recent_title": "Últimos movimientos",
    "toast_new_invoice": "Nueva factura detectada: {proveedor} — €{total:.2f}"
  },
  "scanner": {
    "title": "Escáner de Facturas",
    "subtitle": "Sube, fotografía o introduce tu factura. La IA clasifica automáticamente.",
    "method_upload": "Subir archivo",
    "method_camera": "Hacer foto",
    "method_manual": "Introducir manualmente",
    "upload_label": "Arrastra tu factura aquí",
    "camera_label": "Apunta la cámara a tu factura o recibo",
    "btn_analyze": "Analizar con IA",
    "spinner_analyzing": "Procesando con OCR y Claude... (5-10 segundos)",
    "results_title": "Resultado del análisis",
    "col_extracted": "Datos extraídos",
    "col_verdict": "Clasificación fiscal",
    "col_edit": "Corregir si es necesario",
    "metric_proveedor": "Proveedor",
    "metric_fecha": "Fecha",
    "metric_base": "Base imponible",
    "metric_iva": "IVA",
    "metric_total": "Total",
    "verdict_iva_label": "IVA: {pct}% ({label})",
    "verdict_deducible_100": "100% deducible

€{amount:.2f} deducible",
    "verdict_deducible_partial": "{pct}% deducible

€{deducible:.2f} de €{total:.2f}",
    "verdict_no_deducible": "No deducible",
    "edit_expander": "Editar extracción",
    "edit_proveedor": "Proveedor",
    "edit_fecha": "Fecha (YYYY-MM-DD)",
    "edit_base": "Base imponible",
    "edit_iva": "Tipo IVA",
    "edit_concepto": "Concepto",
    "btn_apply_edits": "Aplicar correcciones",
    "btn_save": "Guardar en mi libro de cuentas",
    "save_success": "Factura de {proveedor} guardada. IVA deducible registrado: €{amount:.2f}",
    "recent_title": "Últimas facturas registradas",
    "iva_discrepancy": "Discrepancia en IVA: factura dice €{extracted:.2f}, calculado €{calculated:.2f}. Verifica la factura.",
    "error_ocr_failed": "Error procesando el documento: {error}",
    "error_ocr_hint": "Prueba a mejorar la iluminación o usa la entrada manual.",
    "manual_proveedor": "Proveedor *",
    "manual_fecha": "Fecha factura",
    "manual_concepto": "Concepto *",
    "manual_concepto_placeholder": "Hosting web, Formación Python...",
    "manual_numero": "Nº Factura",
    "manual_base": "Base imponible (€) *",
    "manual_tipo_iva": "Tipo IVA",
    "manual_cuota_calculated": "Cuota IVA calculada",
    "manual_total": "Total factura",
    "manual_btn_submit": "Clasificar con IA →"
  },
  "agenda": {
    "title": "Mi Agenda y Facturación",
    "tab_upcoming": "Próximas Citas",
    "tab_invoices": "Facturas Emitidas",
    "tab_aging": "AR Aging",
    "no_calendly": "Conecta Calendly en el sidebar para ver tus citas automáticamente.",
    "no_calendly_hint": "Sin Calendly, puedes añadir ingresos manualmente desde el escáner.",
    "btn_generate_invoice": "Generar factura",
    "metric_total_invoiced": "Total facturado",
    "metric_pending": "Pendiente de cobro",
    "aging_title": "Facturas pendientes de cobro"
  },
  "fpa": {
    "title": "Mi Trimestre — FP&A",
    "subtitle": "Proyección fiscal en tiempo real basada en tus datos reales",
    "quarter_selector": "Trimestre",
    "simulator_title": "Simulador 'Y si...'",
    "slider_extra_ingresos": "Ingresos adicionales esperados este trimestre (€)",
    "slider_extra_ingresos_help": "¿Tienes proyectos en pipeline? Añádelos para ver el impacto",
    "slider_extra_gastos": "Gastos deducibles pendientes de este trimestre (€)",
    "slider_extra_gastos_help": "Facturas de gastos aún no escaneadas que sabes que tienes",
    "m303_title": "Modelo 303 — Liquidación IVA",
    "m303_cobrado": "IVA Cobrado (repercutido)",
    "m303_soportado": "IVA Pagado deducible (soportado)",
    "m303_a_pagar": "A pagar a Hacienda",
    "m303_a_compensar": "A compensar próximo trimestre",
    "m130_title": "Modelo 130 — Pago Fraccionado IRPF",
    "m130_ingresos": "Ingresos YTD",
    "m130_gastos": "Gastos deducibles YTD",
    "m130_pago": "Pago fraccionado (20%)",
    "cashflow_title": "Cashflow proyectado",
    "cashflow_summary": "**Resumen del trimestre:**
Ingresos: €{ingresos:,.2f}
Gastos deducibles: €{gastos:,.2f}
**Beneficio neto estimado: €{beneficio:,.2f}**

Reserva sugerida para impuestos: €{reserva:,.2f}",
    "deadline_title": "Próximos plazos",
    "deadline_metric": "{modelo} — {date}",
    "deadline_days": "{days} días restantes"
  },
  "chatbot": {
    "title": "El Gestor — Tu Asesor Fiscal IA",
    "disclaimer": "El Gestor te orienta basándose en tus datos reales. No reemplaza a un gestor para declaraciones oficiales.",
    "placeholder": "Pregunta a El Gestor...",
    "spinner": "El Gestor está pensando...",
    "suggestions_label": "Prueba a preguntar:",
    "suggestion_1": "¿Cuánto debo para el 303 este trimestre?",
    "suggestion_2": "¿Puedo deducir mi portátil nuevo?",
    "suggestion_3": "¿Qué pasa si facturo €3.000 más este mes?"
  },
  "tax_terms": {
    "modelo_303": "Modelo 303",
    "modelo_303_tooltip": "",
    "modelo_130": "Modelo 130",
    "modelo_130_tooltip": "",
    "cuota_ss": "Cuota SS",
    "cuota_ss_tooltip": "",
    "iva_repercutido": "IVA repercutido",
    "iva_repercutido_tooltip": "",
    "iva_soportado": "IVA soportado",
    "iva_soportado_tooltip": "",
    "base_imponible": "Base imponible",
    "base_imponible_tooltip": "",
    "autonomo": "Autónomo",
    "autonomo_tooltip": "",
    "hacienda": "Hacienda",
    "hacienda_tooltip": "",
    "gestor": "Gestor",
    "gestor_tooltip": "",
    "tarifa_plana": "Tarifa Plana",
    "tarifa_plana_tooltip": "",
    "irpf": "IRPF",
    "irpf_tooltip": "",
    "estimacion_directa": "Estimación Directa",
    "estimacion_directa_tooltip": "",
    "tipo_general": "Tipo general",
    "tipo_general_tooltip": "",
    "tipo_reducido": "Tipo reducido",
    "tipo_reducido_tooltip": "",
    "tipo_superreducido": "Tipo superreducido",
    "tipo_superreducido_tooltip": "",
    "exento": "Exento",
    "exento_tooltip": ""
  },
  "common": {
    "disclaimer_tax": "Orientativo. Consulta siempre con tu gestor para declaraciones oficiales.",
    "error_api": "Error de API: {error}",
    "loading": "Cargando...",
    "save": "Guardar",
    "cancel": "Cancelar",
    "edit": "Editar",
    "delete": "Eliminar",
    "confirm": "Confirmar",
    "back": "Volver",
    "next": "Siguiente",
    "yes": "Sí",
    "no": "No",
    "amount_eur": "€{amount:,.2f}",
    "deducible": "Deducible",
    "no_deducible": "No deducible",
    "ingreso": "Ingreso",
    "gasto": "Gasto",
    "pagado": "Pagado",
    "pendiente": "Pendiente",
    "vencido": "Vencido"
  }
}
```

### 12.7 Complete `i18n/en.json`

```json
{
  "app": {
    "name": "Alta Fácil Pro",
    "tagline": "Go freelance, stress-free"
  },
  "nav": {
    "onboarding": "Welcome",
    "dashboard": "Dashboard",
    "scanner": "Invoice Scanner",
    "agenda": "Agenda & AR",
    "fpa": "My Quarter",
    "chatbot": "AI Advisor"
  },
  "sidebar": {
    "greeting": "Hi, {name}",
    "since": "Freelancer since {date}",
    "kpi_revenue": "Revenue this quarter",
    "kpi_iva": "VAT to pay",
    "connect_gmail": "Connect Gmail",
    "gmail_connected": "Gmail connected",
    "connect_calendly": "Connect Calendly",
    "calendly_connected": "Calendly connected",
    "calendly_token_placeholder": "Calendly access token"
  },
  "onboarding": {
    "title": "Welcome to Alta Fácil Pro",
    "subtitle": "Tell us about yourself to personalise your experience",
    "field_name": "Your name",
    "field_name_placeholder": "María García",
    "field_actividad": "What do you do?",
    "field_actividad_placeholder": "Digital marketing consulting, web design...",
    "field_iva_regime": "VAT regime",
    "iva_general": "General regime",
    "iva_simplificado": "Simplified regime",
    "iva_exento": "VAT exempt",
    "field_work_location": "Where do you usually work?",
    "location_casa": "At home (home office)",
    "location_oficina": "At office / coworking",
    "location_mixto": "Mixed",
    "field_home_pct": "% of your home used for work",
    "field_home_pct_help": "Typically between 20% and 30% for a home office",
    "field_tarifa_plana": "I am a new freelancer and have (or will apply for) the Tarifa Plana flat-rate scheme",
    "field_alta_date": "Date you registered as a freelancer (or planned date)",
    "field_irpf": "Income tax withholding on your invoices",
    "field_irpf_help": "New freelancers: 7% for the first 3 years. Standard rate is 15%.",
    "btn_submit": "Start my Alta Fácil Pro →",
    "error_name_required": "Name is required",
    "error_actividad_required": "Activity is required"
  },
  "dashboard": {
    "title": "Good morning, {name}",
    "subtitle": "Summary for {quarter} — updated less than 30 seconds ago",
    "kpi_revenue_label": "Revenue this quarter",
    "kpi_expenses_label": "Deductible expenses",
    "kpi_iva_label": "VAT to settle (approx.)",
    "kpi_irpf_label": "Income tax provision",
    "kpi_irpf_delta": "Set this aside each month",
    "chart_title": "Monthly cashflow",
    "chart_ingresos": "Revenue",
    "chart_gastos": "Expenses",
    "chart_provision": "Tax provision",
    "recent_title": "Recent transactions",
    "toast_new_invoice": "New invoice detected: {proveedor} — €{total:.2f}"
  },
  "scanner": {
    "title": "Invoice Scanner",
    "subtitle": "Upload, photograph or enter your invoice. AI classifies it automatically.",
    "method_upload": "Upload file",
    "method_camera": "Take photo",
    "method_manual": "Enter manually",
    "upload_label": "Drag your invoice here",
    "camera_label": "Point the camera at your invoice or receipt",
    "btn_analyze": "Analyse with AI",
    "spinner_analyzing": "Processing with OCR and Claude... (5-10 seconds)",
    "results_title": "Analysis result",
    "col_extracted": "Extracted data",
    "col_verdict": "Tax classification",
    "col_edit": "Correct if needed",
    "metric_proveedor": "Vendor",
    "metric_fecha": "Date",
    "metric_base": "Net amount (base imponible)",
    "metric_iva": "VAT",
    "metric_total": "Total",
    "verdict_iva_label": "VAT: {pct}% ({label})",
    "verdict_deducible_100": "100% deductible

€{amount:.2f} deductible",
    "verdict_deducible_partial": "{pct}% deductible

€{deducible:.2f} of €{total:.2f}",
    "verdict_no_deducible": "Not deductible",
    "edit_expander": "Edit extraction",
    "edit_proveedor": "Vendor",
    "edit_fecha": "Date (YYYY-MM-DD)",
    "edit_base": "Net amount",
    "edit_iva": "VAT type",
    "edit_concepto": "Description",
    "btn_apply_edits": "Apply corrections",
    "btn_save": "Save to my ledger",
    "save_success": "Invoice from {proveedor} saved. Deductible VAT recorded: €{amount:.2f}",
    "recent_title": "Recent invoices recorded",
    "iva_discrepancy": "VAT discrepancy: invoice says €{extracted:.2f}, calculated €{calculated:.2f}. Please verify.",
    "error_ocr_failed": "Error processing document: {error}",
    "error_ocr_hint": "Try improving the lighting or use manual entry.",
    "manual_proveedor": "Vendor *",
    "manual_fecha": "Invoice date",
    "manual_concepto": "Description *",
    "manual_concepto_placeholder": "Web hosting, Python training...",
    "manual_numero": "Invoice number",
    "manual_base": "Net amount (€) *",
    "manual_tipo_iva": "VAT rate",
    "manual_cuota_calculated": "Calculated VAT",
    "manual_total": "Invoice total",
    "manual_btn_submit": "Classify with AI →"
  },
  "agenda": {
    "title": "Agenda & Invoicing",
    "tab_upcoming": "Upcoming Sessions",
    "tab_invoices": "Issued Invoices",
    "tab_aging": "AR Aging",
    "no_calendly": "Connect Calendly in the sidebar to see your appointments automatically.",
    "no_calendly_hint": "Without Calendly, you can add revenue manually from the scanner.",
    "btn_generate_invoice": "Generate invoice",
    "metric_total_invoiced": "Total invoiced",
    "metric_pending": "Outstanding receivables",
    "aging_title": "Unpaid invoices"
  },
  "fpa": {
    "title": "My Quarter — Financial Planning",
    "subtitle": "Real-time tax projection based on your actual data",
    "quarter_selector": "Quarter",
    "simulator_title": "What-if simulator",
    "slider_extra_ingresos": "Additional expected revenue this quarter (€)",
    "slider_extra_ingresos_help": "Do you have projects in the pipeline? Add them to see the impact",
    "slider_extra_gastos": "Pending deductible expenses this quarter (€)",
    "slider_extra_gastos_help": "Expense invoices you know you have but haven't scanned yet",
    "m303_title": "Modelo 303 (Quarterly VAT Return)",
    "m303_cobrado": "Output VAT (IVA repercutido)",
    "m303_soportado": "Deductible input VAT (IVA soportado)",
    "m303_a_pagar": "To pay to Hacienda (Tax Agency)",
    "m303_a_compensar": "To offset next quarter",
    "m130_title": "Modelo 130 (Quarterly Income Tax Payment)",
    "m130_ingresos": "Revenue YTD",
    "m130_gastos": "Deductible expenses YTD",
    "m130_pago": "Quarterly payment (20%)",
    "cashflow_title": "Projected cashflow",
    "cashflow_summary": "**Quarter summary:**
Revenue: €{ingresos:,.2f}
Deductible expenses: €{gastos:,.2f}
**Estimated net profit: €{beneficio:,.2f}**

Suggested tax reserve: €{reserva:,.2f}",
    "deadline_title": "Upcoming deadlines",
    "deadline_metric": "{modelo} — {date}",
    "deadline_days": "{days} days remaining"
  },
  "chatbot": {
    "title": "AI Tax Advisor",
    "disclaimer": "The AI Advisor guides you based on your real data. It does not replace a professional accountant for official filings.",
    "placeholder": "Ask your tax advisor...",
    "spinner": "Thinking...",
    "suggestions_label": "Try asking:",
    "suggestion_1": "How much VAT do I owe this quarter?",
    "suggestion_2": "Can I deduct my new laptop?",
    "suggestion_3": "What happens if I invoice €3,000 more this month?"
  },
  "tax_terms": {
    "modelo_303": "Modelo 303",
    "modelo_303_tooltip": "Quarterly VAT return. Filed in April, July, October and January.",
    "modelo_130": "Modelo 130",
    "modelo_130_tooltip": "Quarterly income tax prepayment. 20% of net profit, filed same dates as Modelo 303.",
    "cuota_ss": "Cuota SS",
    "cuota_ss_tooltip": "Monthly Social Security contribution paid to Seguridad Social (RETA system).",
    "iva_repercutido": "IVA repercutido",
    "iva_repercutido_tooltip": "Output VAT — the VAT you charge clients on your invoices.",
    "iva_soportado": "IVA soportado",
    "iva_soportado_tooltip": "Input VAT — the VAT you pay on your business expenses.",
    "base_imponible": "Base imponible",
    "base_imponible_tooltip": "Net amount before VAT is added.",
    "autonomo": "Autónomo",
    "autonomo_tooltip": "Self-employed / freelancer status in Spain. Requires registration with Hacienda and Seguridad Social.",
    "hacienda": "Hacienda",
    "hacienda_tooltip": "The Spanish Tax Agency (Agencia Tributaria / AEAT). Manages VAT and income tax.",
    "gestor": "Gestor",
    "gestor_tooltip": "A Spanish accountant/tax advisor. Recommended for official tax filings.",
    "tarifa_plana": "Tarifa Plana",
    "tarifa_plana_tooltip": "Flat-rate Social Security scheme for new freelancers: €80/month for the first 12 months.",
    "irpf": "IRPF",
    "irpf_tooltip": "Personal income tax. Withheld at 15% on most professional invoices.",
    "estimacion_directa": "Estimación Directa",
    "estimacion_directa_tooltip": "Standard income tax calculation: actual income minus actual deductible expenses.",
    "tipo_general": "Tipo general",
    "tipo_general_tooltip": "Standard VAT rate — 21%. Applies to most professional services.",
    "tipo_reducido": "Tipo reducido",
    "tipo_reducido_tooltip": "Reduced VAT rate — 10%. Applies to transport, hospitality, residential construction.",
    "tipo_superreducido": "Tipo superreducido",
    "tipo_superreducido_tooltip": "Super-reduced VAT rate — 4%. Applies to basic foods, medicines, books.",
    "exento": "Exento",
    "exento_tooltip": "VAT exempt — no VAT charged or deductible. Applies to regulated education, healthcare, residential rental."
  },
  "common": {
    "disclaimer_tax": "Indicative only. Always consult your accountant for official filings.",
    "error_api": "API error: {error}",
    "loading": "Loading...",
    "save": "Save",
    "cancel": "Cancel",
    "edit": "Edit",
    "delete": "Delete",
    "confirm": "Confirm",
    "back": "Back",
    "next": "Next",
    "yes": "Yes",
    "no": "No",
    "amount_eur": "€{amount:,.2f}",
    "deducible": "Deductible",
    "no_deducible": "Not deductible",
    "ingreso": "Revenue",
    "gasto": "Expense",
    "pagado": "Paid",
    "pendiente": "Pending",
    "vencido": "Overdue"
  }
}
```

### 12.8 Usage Pattern in Every Page

```python
# At the top of every page file — these 3 imports always together:
from i18n import t, get_lang, set_lang
# Then in render_sidebar(): call render_lang_switcher() first

# Every user-facing string uses t():
st.title(t("dashboard.title", name=profile["nombre"].split()[0]))
st.caption(t("dashboard.subtitle", quarter=quarter))
st.metric(t("dashboard.kpi_revenue_label"), value=f"€{total:,.0f}", delta=t("dashboard.kpi_irpf_delta"))
st.button(t("scanner.btn_analyze"), type="primary")
st.success(t("scanner.save_success", proveedor=result["proveedor"], amount=result["cuota_iva_deducible"]))
st.warning(t("scanner.iva_discrepancy", extracted=2.10, calculated=2.31))
st.caption(t("common.disclaimer_tax"))

# Tax terms always via t():
st.subheader(t("tax_terms.modelo_303"))   # ES: "Modelo 303" | EN: "Modelo 303 (Quarterly VAT Return)"
```

### 12.9 Adding New Strings — Protocol

1. Add the key to `i18n/es.json` first (Spanish is canonical)
2. Add the same key to `i18n/en.json` immediately after
3. Never add a string to one file without the other
4. If a key is missing in `en.json`, `t()` falls back to Spanish silently — acceptable for prototype, not for production

### 12.10 Initialisation in `app.py`

```python
# Add to init_session_state():
if "lang" not in st.session_state:
    st.session_state["lang"] = "es"   # Default Spanish
```

---

*End of specification. Build files in this order: `i18n/__init__.py` → `i18n/es.json` → `i18n/en.json` → `engine/tax_rules.py` → `engine/finance_engine.py` → `engine/invoice_parser.py` → `pages/2_Scanner.py` → `pages/0_Onboarding.py` → `app.py` → `pages/1_Dashboard.py` → `pages/4_FPA.py` → `pages/5_Chatbot.py` → `pages/3_AR_Agenda.py` → `engine/gmail_watcher.py` → `engine/calendly_client.py`*
