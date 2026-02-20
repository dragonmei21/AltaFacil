import json
import unicodedata
from pathlib import Path

# ---------------------------------------------------------------------------
# IRPF annual brackets 2025
# ---------------------------------------------------------------------------
IRPF_BRACKETS = [
    (0, 12450, 0.19),
    (12450, 20200, 0.24),
    (20200, 35200, 0.30),
    (35200, 60000, 0.37),
    (60000, float("inf"), 0.45),
]

# ---------------------------------------------------------------------------
# Social Security (RETA 2025) — 15 brackets
# (net_income_from, net_income_to, monthly_cuota_eur)
# ---------------------------------------------------------------------------
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
    (6000, float("inf"), 1267),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Lowercase, strip accents, strip punctuation."""
    text = text.lower().strip()
    # Strip accents
    nfkd = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Strip punctuation (keep spaces and alphanumeric)
    text = "".join(c if c.isalnum() or c.isspace() else " " for c in text)
    return text


def _keyword_match(text: str, keywords: list[str]) -> str | None:
    """Return the first keyword found in text, or None."""
    normalized = _normalize(text)
    for kw in keywords:
        normalized_kw = _normalize(kw)
        if normalized_kw in normalized:
            return kw
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_tax_rules() -> dict:
    """Load tax_rules_2025.json. Called once, cached with @st.cache_data."""
    path = Path(__file__).parent.parent / "data" / "tax_rules_2025.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def classify_iva(concepto: str, proveedor: str, rules: dict) -> dict:
    """
    Classify IVA rate for an expense/invoice.

    Checks rates in order: 4% -> 10% -> exempt(0%) -> default 21%.
    Returns dict with tipo_iva, label, article, exempt, confidence, match_keyword.
    """
    combined = f"{concepto} {proveedor}"

    # Check 4% superreducido first
    rate_4 = rules["iva_rates"]["4"]
    match = _keyword_match(combined, rate_4["keywords"])
    if match:
        return {
            "tipo_iva": 4,
            "label": rate_4["label"],
            "article": rate_4["article"],
            "exempt": False,
            "confidence": "high",
            "match_keyword": match,
        }

    # Check 10% reducido
    rate_10 = rules["iva_rates"]["10"]
    match = _keyword_match(combined, rate_10["keywords"])
    if match:
        return {
            "tipo_iva": 10,
            "label": rate_10["label"],
            "article": rate_10["article"],
            "exempt": False,
            "confidence": "high",
            "match_keyword": match,
        }

    # Check exempt (0%)
    rate_0 = rules["iva_rates"]["0"]
    match = _keyword_match(combined, rate_0["keywords"])
    if match:
        return {
            "tipo_iva": 0,
            "label": rate_0["label"],
            "article": rate_0["article"],
            "exempt": True,
            "confidence": "high",
            "match_keyword": match,
        }

    # Check 21% general (explicit keyword match = high confidence)
    rate_21 = rules["iva_rates"]["21"]
    match = _keyword_match(combined, rate_21["keywords"])
    if match:
        return {
            "tipo_iva": 21,
            "label": rate_21["label"],
            "article": rate_21["article"],
            "exempt": False,
            "confidence": "high",
            "match_keyword": match,
        }

    # Default: 21% with low confidence (no keyword match)
    return {
        "tipo_iva": 21,
        "label": rate_21["label"],
        "article": rate_21["article"],
        "exempt": False,
        "confidence": "low",
        "match_keyword": "",
    }


def classify_deductibility(
    concepto: str,
    tipo_iva: int,
    exempt: bool,
    user_profile: dict,
    rules: dict,
) -> dict:
    """
    Classify deductibility of IVA soportado.

    Order: exempt -> vehicle(50%) -> home(30% conditional) -> non-deductible(0%)
           -> professional(100%) -> default 100% low confidence.
    """
    ded_rules = rules["deductibility_rules"]

    # 1. If exempt: IVA soportado is never deductible
    if exempt:
        return {
            "deducible": False,
            "porcentaje_deduccion": 0,
            "cuota_iva_deducible": 0.0,
            "justification": "IVA exento — no deducible",
            "article": "Art. 20 Ley 37/1992",
        }

    # 2. Check vehicle keywords -> 50%
    match = _keyword_match(concepto, ded_rules["partial_50"]["keywords"])
    if match:
        return {
            "deducible": True,
            "porcentaje_deduccion": 50,
            "cuota_iva_deducible": 0.0,  # Caller must compute from cuota_iva
            "justification": f"50% deducible — vehículo ({match})",
            "article": ded_rules["partial_50"]["article"],
        }

    # 3. Check home keywords + work_location -> 30% if casa/mixto, else 0%
    match = _keyword_match(concepto, ded_rules["partial_home"]["keywords"])
    if match:
        work_location = user_profile.get("work_location", "oficina")
        if work_location in ("casa", "mixto"):
            pct = user_profile.get("home_office_pct", 30)
            return {
                "deducible": True,
                "porcentaje_deduccion": pct,
                "cuota_iva_deducible": 0.0,
                "justification": f"{pct}% deducible — suministro hogar ({match})",
                "article": ded_rules["partial_home"]["article"],
            }
        else:
            return {
                "deducible": False,
                "porcentaje_deduccion": 0,
                "cuota_iva_deducible": 0.0,
                "justification": "No deducible — trabajas en oficina, no aplica deducción de hogar",
                "article": ded_rules["partial_home"]["article"],
            }

    # 4. Check non-deductible keywords -> 0%
    match = _keyword_match(concepto, ded_rules["zero_0"]["keywords"])
    if match:
        return {
            "deducible": False,
            "porcentaje_deduccion": 0,
            "cuota_iva_deducible": 0.0,
            "justification": f"No deducible — gasto personal ({match})",
            "article": ded_rules["zero_0"]["article"],
        }

    # 5. Check professional keywords -> 100%
    match = _keyword_match(concepto, ded_rules["full_100"]["keywords"])
    if match:
        return {
            "deducible": True,
            "porcentaje_deduccion": 100,
            "cuota_iva_deducible": 0.0,
            "justification": f"100% deducible — gasto profesional ({match})",
            "article": ded_rules["full_100"]["article"],
        }

    # 6. Default: 100% with low confidence
    return {
        "deducible": True,
        "porcentaje_deduccion": 100,
        "cuota_iva_deducible": 0.0,
        "justification": "100% deducible (clasificación automática — verificar)",
        "article": ded_rules["full_100"]["article"],
    }


def calculate_modelo_303(df_quarter) -> dict:
    """
    Calculate Modelo 303 for a given quarter's ledger data.

    Args:
        df_quarter: DataFrame filtered by trimestre (may be empty).
    """
    if df_quarter.empty:
        return {
            "iva_cobrado": 0.0,
            "iva_soportado_total": 0.0,
            "iva_soportado_deducible": 0.0,
            "resultado": 0.0,
            "a_pagar": 0.0,
            "a_compensar": 0.0,
        }

    ingresos = df_quarter[df_quarter["tipo"] == "ingreso"]
    gastos = df_quarter[df_quarter["tipo"] == "gasto"]

    iva_cobrado = float(ingresos["cuota_iva"].sum()) if not ingresos.empty else 0.0
    iva_soportado_total = float(gastos["cuota_iva"].sum()) if not gastos.empty else 0.0
    iva_soportado_deducible = float(gastos["cuota_iva_deducible"].sum()) if not gastos.empty else 0.0

    resultado = iva_cobrado - iva_soportado_deducible

    return {
        "iva_cobrado": iva_cobrado,
        "iva_soportado_total": iva_soportado_total,
        "iva_soportado_deducible": iva_soportado_deducible,
        "resultado": resultado,
        "a_pagar": max(0.0, resultado),
        "a_compensar": abs(min(0.0, resultado)),
    }


def calculate_modelo_130(df_ytd, retenciones_ytd: float = 0.0) -> dict:
    """
    Calculate Modelo 130 pago fraccionado.

    Args:
        df_ytd: All ledger entries from start of year through current quarter.
        retenciones_ytd: Total IRPF retenciones already withheld by clients YTD.
    """
    if df_ytd.empty:
        return {
            "ingresos_ytd": 0.0,
            "gastos_deducibles_ytd": 0.0,
            "beneficio_ytd": 0.0,
            "pago_fraccionado_bruto": 0.0,
            "retenciones_ytd": retenciones_ytd,
            "pago_neto": 0.0,
        }

    ingresos = df_ytd[df_ytd["tipo"] == "ingreso"]
    gastos = df_ytd[df_ytd["tipo"] == "gasto"]

    ingresos_ytd = float(ingresos["base_imponible"].sum()) if not ingresos.empty else 0.0

    # Only deductible expenses count
    gastos_deducibles = gastos[gastos["deducible"] == True] if not gastos.empty else gastos
    gastos_deducibles_ytd = float(gastos_deducibles["base_imponible"].sum()) if not gastos_deducibles.empty else 0.0

    beneficio_ytd = ingresos_ytd - gastos_deducibles_ytd
    pago_fraccionado_bruto = max(0.0, beneficio_ytd * 0.20)
    pago_neto = max(0.0, pago_fraccionado_bruto - retenciones_ytd)

    return {
        "ingresos_ytd": ingresos_ytd,
        "gastos_deducibles_ytd": gastos_deducibles_ytd,
        "beneficio_ytd": beneficio_ytd,
        "pago_fraccionado_bruto": pago_fraccionado_bruto,
        "retenciones_ytd": retenciones_ytd,
        "pago_neto": pago_neto,
    }


def get_cuota_ss(net_monthly_income: float, tarifa_plana: bool, tarifa_plana_active: bool) -> float:
    """
    Get monthly Social Security cuota from RETA 2025 brackets.

    If tarifa_plana and tarifa_plana_active: return 80.0
    Else: iterate SS_BRACKETS, return cuota for matching bracket.
    """
    if tarifa_plana and tarifa_plana_active:
        return 80.0

    for low, high, cuota in SS_BRACKETS:
        if low <= net_monthly_income < high:
            return float(cuota)

    # Shouldn't reach here, but return highest bracket as safety
    return float(SS_BRACKETS[-1][2])
