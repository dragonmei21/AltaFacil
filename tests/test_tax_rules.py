import pandas as pd
import pytest

from engine.tax_rules import (
    calculate_modelo_130,
    calculate_modelo_303,
    classify_deductibility,
    classify_iva,
    get_cuota_ss,
    load_tax_rules,
)


@pytest.fixture(scope="module")
def rules():
    return load_tax_rules()


def test_classify_iva_rates_4_10_0_21(rules):
    # 3+ examples per rate, using keywords from data/tax_rules_2025.json
    cases = [
        # 4% superreducido
        ("Compra de pan", "Panaderia", 4, False),
        ("tampón", "Farmacia", 4, False),
        ("libros infantiles", "Libreria", 4, False),
        # 10% reducido
        ("hostelería", "Hotel Madrid", 10, False),
        ("entrada museo", "Museo Prado", 10, False),
        ("transporte urbano", "Metro", 10, False),
        # 0% exento
        ("consulta médico", "Clinica Salud", 0, True),
        ("formación reglada", "Universidad", 0, True),
        ("psicólogo", "Centro Salud", 0, True),
        # 21% general
        ("consultoría", "Acme", 21, False),
        ("software", "SaaS Inc", 21, False),
        ("electricidad", "Iberdrola", 21, False),
    ]

    for concepto, proveedor, expected_tipo, expected_exempt in cases:
        result = classify_iva(concepto, proveedor, rules)
        assert result["tipo_iva"] == expected_tipo
        assert result["exempt"] == expected_exempt
        assert result["confidence"] == "high"


def test_classify_iva_edge_cases(rules):
    # Empty concept defaults to 21% with low confidence
    result = classify_iva("", "", rules)
    assert result["tipo_iva"] == 21
    assert result["confidence"] == "low"

    # Accents should be normalized and still match
    result = classify_iva("servicio médico", "Clinica", rules)
    assert result["tipo_iva"] == 0
    assert result["exempt"] is True

    # Very long concept should still match if keyword is present
    long_text = " ".join(["texto"] * 200) + " hosting " + " ".join(["mas"] * 200)
    result = classify_iva(long_text, "Proveedor", rules)
    assert result["tipo_iva"] == 21


def test_classify_deductibility_rules(rules):
    base_profile = {"work_location": "oficina", "home_office_pct": 30}

    # Exempt invoices are never deductible
    res = classify_deductibility("médico", 0, True, base_profile, rules)
    assert res["deducible"] is False
    assert res["porcentaje_deduccion"] == 0

    # Vehicle -> 50%
    res = classify_deductibility("gasolina", 21, False, base_profile, rules)
    assert res["deducible"] is True
    assert res["porcentaje_deduccion"] == 50

    # Home expenses -> 30% if casa, 0% if oficina, 30%/mixto uses profile pct
    casa_profile = {"work_location": "casa", "home_office_pct": 30}
    res = classify_deductibility("electricidad", 21, False, casa_profile, rules)
    assert res["deducible"] is True
    assert res["porcentaje_deduccion"] == 30

    oficina_profile = {"work_location": "oficina", "home_office_pct": 30}
    res = classify_deductibility("internet", 21, False, oficina_profile, rules)
    assert res["deducible"] is False
    assert res["porcentaje_deduccion"] == 0

    mixto_profile = {"work_location": "mixto", "home_office_pct": 25}
    res = classify_deductibility("agua", 21, False, mixto_profile, rules)
    assert res["deducible"] is True
    assert res["porcentaje_deduccion"] == 25

    # Non-deductible -> 0%
    res = classify_deductibility("ropa", 21, False, base_profile, rules)
    assert res["deducible"] is False
    assert res["porcentaje_deduccion"] == 0

    # Professional -> 100%
    res = classify_deductibility("software", 21, False, base_profile, rules)
    assert res["deducible"] is True
    assert res["porcentaje_deduccion"] == 100


def test_calculate_modelo_303_known_values():
    df = pd.DataFrame(
        [
            {"tipo": "ingreso", "cuota_iva": 100.0, "cuota_iva_deducible": 0.0},
            {"tipo": "ingreso", "cuota_iva": 50.0, "cuota_iva_deducible": 0.0},
            {"tipo": "gasto", "cuota_iva": 20.0, "cuota_iva_deducible": 15.0},
            {"tipo": "gasto", "cuota_iva": 10.0, "cuota_iva_deducible": 5.0},
        ]
    )

    result = calculate_modelo_303(df)
    assert result["iva_cobrado"] == 150.0
    assert result["iva_soportado_total"] == 30.0
    assert result["iva_soportado_deducible"] == 20.0
    assert result["resultado"] == 130.0
    assert result["a_pagar"] == 130.0
    assert result["a_compensar"] == 0.0


def test_calculate_modelo_130_known_values():
    df = pd.DataFrame(
        [
            {"tipo": "ingreso", "base_imponible": 1000.0, "deducible": False},
            {"tipo": "ingreso", "base_imponible": 500.0, "deducible": False},
            {"tipo": "gasto", "base_imponible": 300.0, "deducible": True},
            {"tipo": "gasto", "base_imponible": 200.0, "deducible": False},
        ]
    )

    result = calculate_modelo_130(df, retenciones_ytd=50.0)
    assert result["ingresos_ytd"] == 1500.0
    assert result["gastos_deducibles_ytd"] == 300.0
    assert result["beneficio_ytd"] == 1200.0
    assert result["pago_fraccionado_bruto"] == 240.0
    assert result["retenciones_ytd"] == 50.0
    assert result["pago_neto"] == 190.0


def test_get_cuota_ss_brackets():
    # Tarifa plana overrides brackets
    assert get_cuota_ss(500.0, tarifa_plana=True, tarifa_plana_active=True) == 80.0

    # Representative brackets
    assert get_cuota_ss(500.0, tarifa_plana=False, tarifa_plana_active=False) == 200.0
    assert get_cuota_ss(800.0, tarifa_plana=False, tarifa_plana_active=False) == 275.0
    assert get_cuota_ss(1000.0, tarifa_plana=False, tarifa_plana_active=False) == 291.0
    assert get_cuota_ss(1600.0, tarifa_plana=False, tarifa_plana_active=False) == 370.0
    assert get_cuota_ss(2500.0, tarifa_plana=False, tarifa_plana_active=False) == 530.0
    assert get_cuota_ss(7000.0, tarifa_plana=False, tarifa_plana_active=False) == 1267.0
