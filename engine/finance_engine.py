import pandas as pd
import uuid
from datetime import datetime, date
from pathlib import Path

LEDGER_PATH = Path(__file__).parent.parent / "data" / "ledger.csv"

LEDGER_COLUMNS = [
    "id", "fecha", "tipo", "proveedor_cliente", "nif", "concepto",
    "numero_factura", "base_imponible", "tipo_iva", "cuota_iva", "total",
    "deducible", "porcentaje_deduccion", "cuota_iva_deducible", "aeat_articulo",
    "trimestre", "estado", "origen",
]

_DTYPES = {
    "id": str,
    "fecha": str,
    "tipo": str,
    "proveedor_cliente": str,
    "nif": str,
    "concepto": str,
    "numero_factura": str,
    "base_imponible": float,
    "tipo_iva": int,
    "cuota_iva": float,
    "total": float,
    "deducible": bool,
    "porcentaje_deduccion": int,
    "cuota_iva_deducible": float,
    "aeat_articulo": str,
    "trimestre": str,
    "estado": str,
    "origen": str,
}


def load_ledger() -> pd.DataFrame:
    """
    Load ledger.csv. Create with correct columns if not exists.
    Returns DataFrame with correct dtypes.
    """
    if not LEDGER_PATH.exists():
        LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(columns=LEDGER_COLUMNS)
        df.to_csv(LEDGER_PATH, index=False)
        return _apply_dtypes(df)

    df = pd.read_csv(LEDGER_PATH, dtype=str, keep_default_na=False)
    return _apply_dtypes(df)


def _apply_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Apply correct dtypes to ledger DataFrame."""
    if df.empty:
        for col, dtype in _DTYPES.items():
            if col in df.columns:
                df[col] = df[col].astype(dtype) if dtype != bool else df[col]
        return df

    float_cols = ["base_imponible", "cuota_iva", "total", "cuota_iva_deducible"]
    int_cols = ["tipo_iva", "porcentaje_deduccion"]

    for col in float_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    for col in int_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    if "deducible" in df.columns:
        df["deducible"] = df["deducible"].map(
            {"True": True, "true": True, "1": True, "False": False, "false": False, "0": False}
        ).fillna(False)

    return df


def save_to_ledger(entry: dict) -> str:
    """
    Append one entry to ledger.csv.
    Generates UUID4 id, derives trimestre from fecha, fills defaults.
    Returns the generated UUID id string.
    """
    # Fill defaults
    entry_id = str(uuid.uuid4())
    entry["id"] = entry_id

    if "trimestre" not in entry or not entry["trimestre"]:
        entry["trimestre"] = _derive_quarter(entry.get("fecha", ""))

    entry.setdefault("estado", "pendiente")
    entry.setdefault("nif", "")
    entry.setdefault("numero_factura", "")

    # Ensure all columns exist
    row = {col: entry.get(col, "") for col in LEDGER_COLUMNS}

    # Load existing, append, save
    df = load_ledger()
    new_row = pd.DataFrame([row])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(LEDGER_PATH, index=False)

    return entry_id


def _derive_quarter(fecha_str: str) -> str:
    """Derive quarter string from date string YYYY-MM-DD."""
    if not fecha_str:
        return get_current_quarter()
    try:
        d = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        return get_current_quarter(d)
    except ValueError:
        return get_current_quarter()


def get_current_quarter(d: date = None) -> str:
    """
    Return quarter string for a date.
    e.g. date(2025, 4, 15) -> "2025-Q2"
    """
    if d is None:
        d = date.today()
    q = (d.month - 1) // 3 + 1
    return f"{d.year}-Q{q}"


def get_quarterly_summary(df: pd.DataFrame, quarter: str) -> dict:
    """
    Return summary dict for a given quarter.
    Returns zeros for empty datasets (never NaN).
    """
    qdf = df[df["trimestre"] == quarter] if not df.empty else df

    if qdf.empty:
        return {
            "total_ingresos": 0.0,
            "total_gastos_base": 0.0,
            "total_gastos_deducibles": 0.0,
            "iva_cobrado": 0.0,
            "iva_soportado_deducible": 0.0,
            "resultado_303": 0.0,
            "beneficio_neto": 0.0,
            "irpf_provision": 0.0,
            "n_facturas": 0,
            "n_gastos": 0,
        }

    ingresos = qdf[qdf["tipo"] == "ingreso"]
    gastos = qdf[qdf["tipo"] == "gasto"]

    total_ingresos = float(ingresos["base_imponible"].sum()) if not ingresos.empty else 0.0
    total_gastos_base = float(gastos["base_imponible"].sum()) if not gastos.empty else 0.0

    gastos_deducibles = gastos[gastos["deducible"] == True] if not gastos.empty else gastos
    total_gastos_deducibles = float(gastos_deducibles["base_imponible"].sum()) if not gastos_deducibles.empty else 0.0

    iva_cobrado = float(ingresos["cuota_iva"].sum()) if not ingresos.empty else 0.0
    iva_soportado_deducible = float(gastos["cuota_iva_deducible"].sum()) if not gastos.empty else 0.0

    resultado_303 = iva_cobrado - iva_soportado_deducible
    beneficio_neto = total_ingresos - total_gastos_deducibles
    irpf_provision = beneficio_neto * 0.20

    return {
        "total_ingresos": total_ingresos,
        "total_gastos_base": total_gastos_base,
        "total_gastos_deducibles": total_gastos_deducibles,
        "iva_cobrado": iva_cobrado,
        "iva_soportado_deducible": iva_soportado_deducible,
        "resultado_303": resultado_303,
        "beneficio_neto": beneficio_neto,
        "irpf_provision": irpf_provision,
        "n_facturas": len(ingresos),
        "n_gastos": len(gastos),
    }


def get_monthly_breakdown(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """
    Returns DataFrame with columns: month (1-12), ingresos, gastos_base, tax_provision.
    Always returns all 12 months even if no data.
    """
    result = []
    for month in range(1, 13):
        if df.empty:
            result.append({"month": month, "ingresos": 0.0, "gastos_base": 0.0, "tax_provision": 0.0})
            continue

        # Filter by year and month from fecha string
        mask = df["fecha"].str.startswith(f"{year}-{month:02d}")
        mdf = df[mask]

        if mdf.empty:
            result.append({"month": month, "ingresos": 0.0, "gastos_base": 0.0, "tax_provision": 0.0})
            continue

        ingresos = mdf[mdf["tipo"] == "ingreso"]
        gastos = mdf[mdf["tipo"] == "gasto"]

        ing_total = float(ingresos["base_imponible"].sum()) if not ingresos.empty else 0.0
        gas_total = float(gastos["base_imponible"].sum()) if not gastos.empty else 0.0
        tax_provision = (ing_total - gas_total) * 0.20

        result.append({
            "month": month,
            "ingresos": ing_total,
            "gastos_base": gas_total,
            "tax_provision": max(0.0, tax_provision),
        })

    return pd.DataFrame(result)


def get_ar_aging(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter ingresos with estado != 'pagado'.
    Calculate days_outstanding and aging_bucket.
    """
    if df.empty:
        return pd.DataFrame(columns=LEDGER_COLUMNS + ["days_outstanding", "aging_bucket"])

    pending = df[(df["tipo"] == "ingreso") & (df["estado"] != "pagado")].copy()

    if pending.empty:
        return pd.DataFrame(columns=list(pending.columns) + ["days_outstanding", "aging_bucket"])

    today = date.today()
    pending["days_outstanding"] = pending["fecha"].apply(
        lambda x: (today - datetime.strptime(x, "%Y-%m-%d").date()).days if x else 0
    )

    def bucket(days):
        if days <= 30:
            return "0-30"
        elif days <= 60:
            return "31-60"
        elif days <= 90:
            return "61-90"
        return "90+"

    pending["aging_bucket"] = pending["days_outstanding"].apply(bucket)
    return pending.sort_values("fecha", ascending=True)


def get_ytd_summary(df: pd.DataFrame, year: int, through_quarter: int) -> dict:
    """
    Return YTD totals from Q1 through through_quarter (inclusive).
    Same structure as get_quarterly_summary().
    """
    quarters = [f"{year}-Q{q}" for q in range(1, through_quarter + 1)]

    if df.empty:
        return get_quarterly_summary(df, "")

    ytd = df[df["trimestre"].isin(quarters)]
    # Reuse quarterly summary logic on the combined data
    return _summarize(ytd)


def _summarize(qdf: pd.DataFrame) -> dict:
    """Internal summary logic shared by quarterly and YTD."""
    if qdf.empty:
        return {
            "total_ingresos": 0.0,
            "total_gastos_base": 0.0,
            "total_gastos_deducibles": 0.0,
            "iva_cobrado": 0.0,
            "iva_soportado_deducible": 0.0,
            "resultado_303": 0.0,
            "beneficio_neto": 0.0,
            "irpf_provision": 0.0,
            "n_facturas": 0,
            "n_gastos": 0,
        }

    ingresos = qdf[qdf["tipo"] == "ingreso"]
    gastos = qdf[qdf["tipo"] == "gasto"]

    total_ingresos = float(ingresos["base_imponible"].sum()) if not ingresos.empty else 0.0
    total_gastos_base = float(gastos["base_imponible"].sum()) if not gastos.empty else 0.0

    gastos_deducibles = gastos[gastos["deducible"] == True] if not gastos.empty else gastos
    total_gastos_deducibles = float(gastos_deducibles["base_imponible"].sum()) if not gastos_deducibles.empty else 0.0

    iva_cobrado = float(ingresos["cuota_iva"].sum()) if not ingresos.empty else 0.0
    iva_soportado_deducible = float(gastos["cuota_iva_deducible"].sum()) if not gastos.empty else 0.0

    resultado_303 = iva_cobrado - iva_soportado_deducible
    beneficio_neto = total_ingresos - total_gastos_deducibles
    irpf_provision = beneficio_neto * 0.20

    return {
        "total_ingresos": total_ingresos,
        "total_gastos_base": total_gastos_base,
        "total_gastos_deducibles": total_gastos_deducibles,
        "iva_cobrado": iva_cobrado,
        "iva_soportado_deducible": iva_soportado_deducible,
        "resultado_303": resultado_303,
        "beneficio_neto": beneficio_neto,
        "irpf_provision": irpf_provision,
        "n_facturas": len(ingresos),
        "n_gastos": len(gastos),
    }
