"""
seed_demo_data.py — Populate Alta Fácil Pro with realistic demo data.

Creates:
  - data/user_profile.json  (María García, marketing consultant, home office)
  - data/ledger.csv         (15 entries: 8 gastos + 7 ingresos across Q1/Q2 2025)

Run from project root:
    python scripts/seed_demo_data.py
"""

import csv
import json
import uuid
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

PROFILE_PATH = DATA_DIR / "user_profile.json"
LEDGER_PATH = DATA_DIR / "ledger.csv"

LEDGER_COLUMNS = [
    "id", "fecha", "tipo", "proveedor_cliente", "nif", "concepto",
    "numero_factura", "base_imponible", "tipo_iva", "cuota_iva", "total",
    "deducible", "porcentaje_deduccion", "cuota_iva_deducible", "aeat_articulo",
    "trimestre", "estado", "origen",
]


# ── User Profile ───────────────────────────────────────────────────────────────
PROFILE = {
    "nombre": "María García",
    "actividad": "Consultoría de marketing digital",
    "iae_code": "702",
    "iva_regime": "general",
    "irpf_retencion_pct": 15,
    "work_location": "casa",
    "home_office_pct": 30,
    "ss_bracket_monthly": 291,
    "tarifa_plana": True,
    "tarifa_plana_end_date": "2024-12-31",   # ended — no longer active
    "alta_date": "2024-01-01",
    "autonomia": "peninsular",
    "onboarding_complete": True,
}


# ── Helper ─────────────────────────────────────────────────────────────────────
def row(
    fecha: str,
    tipo: str,
    proveedor_cliente: str,
    concepto: str,
    base_imponible: float,
    tipo_iva: int,
    deducible: bool,
    porcentaje_deduccion: int,
    aeat_articulo: str,
    estado: str,
    origen: str = "manual",
    nif: str = "",
    numero_factura: str = "",
) -> dict:
    cuota_iva = round(base_imponible * tipo_iva / 100, 2)
    total = round(base_imponible + cuota_iva, 2)
    cuota_iva_deducible = round(cuota_iva * porcentaje_deduccion / 100, 2)
    year = fecha[:4]
    month = int(fecha[5:7])
    quarter = (month - 1) // 3 + 1
    trimestre = f"{year}-Q{quarter}"

    return {
        "id": str(uuid.uuid4()),
        "fecha": fecha,
        "tipo": tipo,
        "proveedor_cliente": proveedor_cliente,
        "nif": nif,
        "concepto": concepto,
        "numero_factura": numero_factura,
        "base_imponible": base_imponible,
        "tipo_iva": tipo_iva,
        "cuota_iva": cuota_iva,
        "total": total,
        "deducible": deducible,
        "porcentaje_deduccion": porcentaje_deduccion,
        "cuota_iva_deducible": cuota_iva_deducible,
        "aeat_articulo": aeat_articulo,
        "trimestre": trimestre,
        "estado": estado,
        "origen": origen,
    }


# ── Ledger entries ─────────────────────────────────────────────────────────────
ENTRIES = [
    # ── GASTOS (8) ──────────────────────────────────────────────────────────────

    # 1. AWS hosting — Q1, 100% deductible, 21%
    row(
        fecha="2025-01-15",
        tipo="gasto",
        proveedor_cliente="Amazon Web Services EMEA SARL",
        concepto="Hosting EC2 + S3 — enero 2025",
        base_imponible=89.99,
        tipo_iva=21,
        deducible=True,
        porcentaje_deduccion=100,
        aeat_articulo="Art. 28-30 Ley 35/2006 IRPF",
        estado="pagado",
        nif="ESB64772878",
        numero_factura="AWS-2025-01-0042",
    ),

    # 2. Notion SaaS — Q1, 100% deductible, 21%
    row(
        fecha="2025-01-20",
        tipo="gasto",
        proveedor_cliente="Notion Labs Inc.",
        concepto="Suscripción Notion Plus — enero 2025",
        base_imponible=14.87,
        tipo_iva=21,
        deducible=True,
        porcentaje_deduccion=100,
        aeat_articulo="Art. 28-30 Ley 35/2006 IRPF",
        estado="pagado",
        numero_factura="NOTION-2501",
    ),

    # 3. Formación Python — Q1, 100% deductible, 21%
    row(
        fecha="2025-02-05",
        tipo="gasto",
        proveedor_cliente="Udemy Ireland UC",
        concepto="Curso Python para análisis de datos",
        base_imponible=19.99,
        tipo_iva=21,
        deducible=True,
        porcentaje_deduccion=100,
        aeat_articulo="Art. 28-30 Ley 35/2006 IRPF",
        estado="pagado",
        numero_factura="UD-ES-20250205",
    ),

    # 4. Renfe — Q1, 10% reducido, 100% deductible (business travel)
    row(
        fecha="2025-02-18",
        tipo="gasto",
        proveedor_cliente="Renfe Operadora",
        concepto="Billete AVE Madrid-Barcelona (reunión cliente)",
        base_imponible=45.00,
        tipo_iva=10,
        deducible=True,
        porcentaje_deduccion=100,
        aeat_articulo="Art. 28-30 Ley 35/2006 IRPF",
        estado="pagado",
        nif="ESQ2801660H",
        numero_factura="RNF-250218-0091",
    ),

    # 5. Coworking — Q1, 21%, 100% deductible
    row(
        fecha="2025-03-01",
        tipo="gasto",
        proveedor_cliente="Regus España SL",
        concepto="Alquiler sala reuniones coworking — marzo",
        base_imponible=80.00,
        tipo_iva=21,
        deducible=True,
        porcentaje_deduccion=100,
        aeat_articulo="Art. 28-30 Ley 35/2006 IRPF",
        estado="pagado",
        nif="ESB82387770",
        numero_factura="RGS-MAR25-0034",
    ),

    # 6. Electricidad — Q2, 21%, 30% deductible (home office)
    row(
        fecha="2025-04-10",
        tipo="gasto",
        proveedor_cliente="Endesa Energía SAU",
        concepto="Factura luz — abril 2025",
        base_imponible=62.50,
        tipo_iva=21,
        deducible=True,
        porcentaje_deduccion=30,
        aeat_articulo="Art. 30 Ley 35/2006 IRPF",
        estado="pagado",
        nif="ESA81948077",
        numero_factura="END-APR25-7812",
    ),

    # 7. Gasolina — Q2, 21%, 50% deductible (vehicle)
    row(
        fecha="2025-05-08",
        tipo="gasto",
        proveedor_cliente="Repsol YPF SA",
        concepto="Gasolina — visita cliente Valencia",
        base_imponible=55.00,
        tipo_iva=21,
        deducible=True,
        porcentaje_deduccion=50,
        aeat_articulo="Art. 95.Tres Ley 37/1992 LIVA",
        estado="pagado",
        nif="ESA78052828",
    ),

    # 8. Gestor / asesoría — Q2, 21%, 100% deductible
    row(
        fecha="2025-06-03",
        tipo="gasto",
        proveedor_cliente="Asesoría Fiscal Martínez SLP",
        concepto="Honorarios gestoría — presentación Modelo 130 Q1",
        base_imponible=120.00,
        tipo_iva=21,
        deducible=True,
        porcentaje_deduccion=100,
        aeat_articulo="Art. 28-30 Ley 35/2006 IRPF",
        estado="pagado",
        nif="ESB12345678",
        numero_factura="AFM-2025-042",
    ),

    # ── INGRESOS (7) ────────────────────────────────────────────────────────────

    # 1. Strategy consultation — Q1, pagado
    row(
        fecha="2025-01-28",
        tipo="ingreso",
        proveedor_cliente="TechStartup SL",
        concepto="Consultoría estrategia de marketing digital — enero",
        base_imponible=1500.00,
        tipo_iva=21,
        deducible=False,
        porcentaje_deduccion=0,
        aeat_articulo="",
        estado="pagado",
        nif="ESB98765432",
        numero_factura="FAC-2025-001",
        origen="manual",
    ),

    # 2. SEO audit — Q1, pagado
    row(
        fecha="2025-02-14",
        tipo="ingreso",
        proveedor_cliente="Moda Española SL",
        concepto="Auditoría SEO y plan de contenidos",
        base_imponible=850.00,
        tipo_iva=21,
        deducible=False,
        porcentaje_deduccion=0,
        aeat_articulo="",
        estado="pagado",
        nif="ESB11223344",
        numero_factura="FAC-2025-002",
        origen="manual",
    ),

    # 3. Social media management — Q1, pagado
    row(
        fecha="2025-03-20",
        tipo="ingreso",
        proveedor_cliente="Restaurante El Patio SL",
        concepto="Gestión redes sociales — marzo 2025",
        base_imponible=600.00,
        tipo_iva=21,
        deducible=False,
        porcentaje_deduccion=0,
        aeat_articulo="",
        estado="pagado",
        nif="ESB55667788",
        numero_factura="FAC-2025-003",
        origen="manual",
    ),

    # 4. Google Ads campaign — Q2, pendiente
    row(
        fecha="2025-04-22",
        tipo="ingreso",
        proveedor_cliente="TechStartup SL",
        concepto="Gestión campaña Google Ads — abril 2025",
        base_imponible=1200.00,
        tipo_iva=21,
        deducible=False,
        porcentaje_deduccion=0,
        aeat_articulo="",
        estado="pendiente",
        nif="ESB98765432",
        numero_factura="FAC-2025-004",
        origen="calendly",
    ),

    # 5. Brand identity — Q2, pendiente
    row(
        fecha="2025-05-10",
        tipo="ingreso",
        proveedor_cliente="Farmacia Sánchez",
        concepto="Identidad de marca y guía de estilo",
        base_imponible=950.00,
        tipo_iva=21,
        deducible=False,
        porcentaje_deduccion=0,
        aeat_articulo="",
        estado="pendiente",
        nif="ESB33445566",
        numero_factura="FAC-2025-005",
        origen="manual",
    ),

    # 6. Email marketing — Q2, pendiente
    row(
        fecha="2025-05-28",
        tipo="ingreso",
        proveedor_cliente="Moda Española SL",
        concepto="Estrategia email marketing + 4 newsletters",
        base_imponible=700.00,
        tipo_iva=21,
        deducible=False,
        porcentaje_deduccion=0,
        aeat_articulo="",
        estado="pendiente",
        nif="ESB11223344",
        numero_factura="FAC-2025-006",
        origen="manual",
    ),

    # 7. Analytics dashboard — Q2, pendiente (vencido)
    row(
        fecha="2025-04-05",
        tipo="ingreso",
        proveedor_cliente="Distribuciones López SA",
        concepto="Dashboard analítica web — Looker Studio",
        base_imponible=400.00,
        tipo_iva=21,
        deducible=False,
        porcentaje_deduccion=0,
        aeat_articulo="",
        estado="vencido",
        nif="ESA77889900",
        numero_factura="FAC-2025-007",
        origen="manual",
    ),
]


# ── Write files ────────────────────────────────────────────────────────────────
def seed():
    # User profile
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(PROFILE, f, ensure_ascii=False, indent=2)
    print(f"✅ Wrote {PROFILE_PATH}")

    # Ledger CSV
    with open(LEDGER_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_COLUMNS)
        writer.writeheader()
        for entry in ENTRIES:
            writer.writerow(entry)
    print(f"✅ Wrote {LEDGER_PATH} ({len(ENTRIES)} entries)")

    # Summary
    gastos = [e for e in ENTRIES if e["tipo"] == "gasto"]
    ingresos = [e for e in ENTRIES if e["tipo"] == "ingreso"]
    total_ingresos = sum(e["base_imponible"] for e in ingresos)
    total_gastos = sum(e["base_imponible"] for e in gastos)
    print(f"\n   Gastos:   {len(gastos)} entries, base total €{total_gastos:,.2f}")
    print(f"   Ingresos: {len(ingresos)} entries, base total €{total_ingresos:,.2f}")
    print(f"   Quarters: Q1 2025 + Q2 2025")


if __name__ == "__main__":
    seed()
