import pandas as pd
from datetime import date

import pytest

import engine.finance_engine as fe


@pytest.fixture()
def temp_ledger(tmp_path, monkeypatch):
    ledger_path = tmp_path / "ledger.csv"
    monkeypatch.setattr(fe, "LEDGER_PATH", ledger_path)
    return ledger_path


def test_load_ledger_creates_file_with_columns(temp_ledger):
    assert not temp_ledger.exists()
    df = fe.load_ledger()
    assert temp_ledger.exists()
    assert list(df.columns) == fe.LEDGER_COLUMNS
    assert df.empty


def test_save_to_ledger_generates_unique_uuid_and_trimestre(temp_ledger):
    entry = {
        "fecha": "2025-05-10",
        "tipo": "gasto",
        "proveedor_cliente": "Proveedor",
        "concepto": "software",
        "base_imponible": 100.0,
        "tipo_iva": 21,
        "cuota_iva": 21.0,
        "total": 121.0,
        "deducible": True,
        "porcentaje_deduccion": 100,
        "cuota_iva_deducible": 21.0,
        "aeat_articulo": "Art. 90.Uno",
        "estado": "pendiente",
        "origen": "manual",
    }

    id1 = fe.save_to_ledger(entry.copy())
    id2 = fe.save_to_ledger(entry.copy())
    assert id1 != id2

    df = fe.load_ledger()
    assert len(df) == 2
    assert df.loc[0, "trimestre"] == "2025-Q2"
    assert df.loc[1, "trimestre"] == "2025-Q2"


def test_get_current_quarter_all_quarters():
    assert fe.get_current_quarter(date(2025, 1, 1)) == "2025-Q1"
    assert fe.get_current_quarter(date(2025, 4, 1)) == "2025-Q2"
    assert fe.get_current_quarter(date(2025, 7, 1)) == "2025-Q3"
    assert fe.get_current_quarter(date(2025, 10, 1)) == "2025-Q4"


def test_get_quarterly_summary_empty_df_returns_zeros():
    df = pd.DataFrame(columns=fe.LEDGER_COLUMNS)
    summary = fe.get_quarterly_summary(df, "2025-Q1")
    assert all(summary[key] == 0 or summary[key] == 0.0 for key in summary)


def test_get_monthly_breakdown_returns_all_months():
    df = pd.DataFrame(columns=fe.LEDGER_COLUMNS)
    result = fe.get_monthly_breakdown(df, 2025)
    assert len(result) == 12
    assert list(result["month"]) == list(range(1, 13))


def test_get_ar_aging_buckets(monkeypatch):
    class FakeDate(date):
        @classmethod
        def today(cls):
            return date(2025, 6, 30)

    monkeypatch.setattr(fe, "date", FakeDate)

    df = pd.DataFrame(
        [
            {"tipo": "ingreso", "estado": "pendiente", "fecha": "2025-06-20"},  # 10 days
            {"tipo": "ingreso", "estado": "pendiente", "fecha": "2025-05-20"},  # 41 days
            {"tipo": "ingreso", "estado": "pendiente", "fecha": "2025-04-01"},  # 90 days
            {"tipo": "ingreso", "estado": "pendiente", "fecha": "2025-01-01"},  # 180 days
            {"tipo": "ingreso", "estado": "pagado", "fecha": "2025-06-10"},
        ]
    )

    aging = fe.get_ar_aging(df)
    buckets = list(aging["aging_bucket"])
    assert buckets == ["90+", "61-90", "31-60", "0-30"]
