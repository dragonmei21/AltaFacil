import os

from openai import OpenAI
import pandas as pd
import pytest

from engine.finance_engine import LEDGER_COLUMNS, load_ledger, save_to_ledger, get_quarterly_summary
from engine.tax_rules import load_tax_rules, classify_iva, classify_deductibility, calculate_modelo_303
from engine.invoice_parser import parse_with_claude


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)
def test_end_to_end_integration(tmp_path, monkeypatch):
    # Use temp ledger so we don't touch real data
    ledger_path = tmp_path / "ledger.csv"
    monkeypatch.setattr("engine.finance_engine.LEDGER_PATH", ledger_path)

    tax_rules = load_tax_rules()
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    raw_text = """
FACTURA
Proveedor: SaaS Tools SL
NIF: B12345678
Fecha: 2025-02-15
Numero factura: F-2025-001
Concepto: Suscripción software mensual
Base imponible: 100.00 EUR
IVA 21%: 21.00 EUR
Total: 121.00 EUR
""".strip()

    parsed = parse_with_claude(raw_text, client)
    assert not parsed.get("parse_error"), f"Claude parse error: {parsed.get('raw', '')}"

    concepto = parsed.get("concepto", "")
    proveedor = parsed.get("proveedor", "")

    iva_result = classify_iva(concepto, proveedor, tax_rules)
    user_profile = {"work_location": "oficina", "home_office_pct": 30}
    ded_result = classify_deductibility(
        concepto,
        iva_result["tipo_iva"],
        iva_result["exempt"],
        user_profile,
        tax_rules,
    )

    base = float(parsed.get("base_imponible", 0))
    cuota_iva = round(base * iva_result["tipo_iva"] / 100, 2)
    cuota_iva_deducible = round(cuota_iva * ded_result["porcentaje_deduccion"] / 100, 2)

    entry = {
        "fecha": parsed.get("fecha", "2025-02-15"),
        "tipo": "gasto",
        "proveedor_cliente": proveedor,
        "nif": parsed.get("nif_proveedor", ""),
        "concepto": concepto,
        "numero_factura": parsed.get("numero_factura", ""),
        "base_imponible": base,
        "tipo_iva": iva_result["tipo_iva"],
        "cuota_iva": cuota_iva,
        "total": round(base + cuota_iva, 2),
        "deducible": ded_result["deducible"],
        "porcentaje_deduccion": ded_result["porcentaje_deduccion"],
        "cuota_iva_deducible": cuota_iva_deducible,
        "aeat_articulo": iva_result["article"],
        "estado": "pendiente",
        "origen": "scanner",
    }

    save_to_ledger(entry)

    df = load_ledger()
    assert len(df) == 1

    quarter = df.loc[0, "trimestre"]
    summary = get_quarterly_summary(df, quarter)

    # IVA values should match our computed values for this expense
    assert summary["iva_cobrado"] == 0.0
    assert summary["iva_soportado_deducible"] == cuota_iva_deducible

    modelo_303 = calculate_modelo_303(df)
    assert modelo_303["resultado"] == modelo_303["iva_cobrado"] - modelo_303["iva_soportado_deducible"]
