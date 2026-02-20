from datetime import date, datetime

import streamlit as st

from engine.finance_engine import (
    load_ledger,
    get_current_quarter,
    get_quarterly_summary,
    get_ytd_summary,
)
from engine.tax_rules import calculate_modelo_130
from i18n import t, tax_header
from shared.sidebar import render_sidebar


def _quarter_options(year: int) -> list[str]:
    """Return the four quarter labels for a given year."""
    return [f"{year}-Q{q}" for q in range(1, 5)]


def _current_quarter_index(options: list[str]) -> int:
    """Return the index of the current quarter in the options list."""
    current = get_current_quarter()
    return options.index(current) if current in options else 0


def get_next_deadline(selected_quarter: str) -> dict:
    """Compute the next filing deadline for the given quarter."""
    year_str, qtr_str = selected_quarter.split("-Q")
    year = int(year_str)
    qtr = int(qtr_str)

    deadline_map = {1: (4, 20), 2: (7, 20), 3: (10, 20), 4: (1, 20)}
    month, day = deadline_map[qtr]
    deadline_year = year + 1 if qtr == 4 else year
    deadline_date = date(deadline_year, month, day)

    today = date.today()
    if deadline_date < today:
        # If the quarter is in the past, show the next quarter's deadline.
        next_q = 1 if qtr == 4 else qtr + 1
        next_year = year + 1 if qtr == 4 else year
        month, day = deadline_map[next_q]
        deadline_year = next_year + 1 if next_q == 4 else next_year
        deadline_date = date(deadline_year, month, day)

    days_remaining = (deadline_date - today).days
    return {
        "modelo": "303/130",
        "deadline_date": deadline_date.isoformat(),
        "days_remaining": days_remaining,
    }


profile = st.session_state.get("user_profile", {})

st.title(t("fpa.title"))
st.caption(t("fpa.subtitle"))

# Quarter selector in sidebar.
year = datetime.now().year
quarters = _quarter_options(year)
selected_quarter = st.sidebar.selectbox(
    t("fpa.quarter_selector"),
    options=quarters,
    index=_current_quarter_index(quarters),
)

df = load_ledger()
summary = get_quarterly_summary(df, selected_quarter)
render_sidebar(profile, summary)

# What-if simulator sliders.
st.subheader(t("fpa.simulator_title"))
col_s1, col_s2 = st.columns(2)
with col_s1:
    extra_ingresos = st.slider(
        t("fpa.slider_extra_ingresos"),
        min_value=0,
        max_value=20000,
        value=0,
        step=500,
        help=t("fpa.slider_extra_ingresos_help"),
    )
with col_s2:
    extra_gastos = st.slider(
        t("fpa.slider_extra_gastos"),
        min_value=0,
        max_value=10000,
        value=0,
        step=100,
        help=t("fpa.slider_extra_gastos_help"),
    )

# Recalculate with slider values.
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

# Modelo 303 section.
tax_header("modelo_303")
with st.expander(t("fpa.m303_title"), expanded=True):
    col1, col2, col3 = st.columns(3)
    col1.metric(t("fpa.m303_cobrado"), f"€{adj_summary['iva_cobrado']:,.2f}")
    col2.metric(t("fpa.m303_soportado"), f"€{adj_summary['iva_soportado_deducible']:,.2f}")
    resultado = adj_summary["resultado_303"]
    if resultado >= 0:
        col3.metric(t("fpa.m303_a_pagar"), f"€{resultado:,.2f}")
    else:
        col3.metric(t("fpa.m303_a_compensar"), f"€{abs(resultado):,.2f}")

# Modelo 130 section.
tax_header("modelo_130")
with st.expander(t("fpa.m130_title"), expanded=True):
    year_int = int(selected_quarter.split("-")[0])
    ytd = get_ytd_summary(df, year_int, int(selected_quarter[-1]))
    m130 = calculate_modelo_130(df[df["trimestre"].str.startswith(str(year_int))], retenciones_ytd=0)
    col1, col2, col3 = st.columns(3)
    col1.metric(t("fpa.m130_ingresos"), f"€{m130['ingresos_ytd']:,.2f}")
    col2.metric(t("fpa.m130_gastos"), f"€{m130['gastos_deducibles_ytd']:,.2f}")
    col3.metric(t("fpa.m130_pago"), f"€{m130['pago_neto']:,.2f}")

# Cashflow projection.
with st.expander(t("fpa.cashflow_title"), expanded=False):
    reserva = adj_summary["irpf_provision"] + max(0, resultado)
    st.info(
        t(
            "fpa.cashflow_summary",
            ingresos=f"{adj_summary['total_ingresos']:,.2f}",
            gastos=f"{adj_summary['total_gastos_deducibles']:,.2f}",
            beneficio=f"{adj_summary['beneficio_neto']:,.2f}",
            reserva=f"{reserva:,.2f}",
        )
    )

# Deadline countdown.
st.subheader(t("fpa.deadline_title"))
deadline_info = get_next_deadline(selected_quarter)
days = deadline_info["days_remaining"]
progress_val = max(0, min(1, 1 - days / 90))
color = "normal" if days > 30 else ("off" if days > 15 else "inverse")
st.metric(
    t("fpa.deadline_metric", modelo=deadline_info["modelo"], date=deadline_info["deadline_date"]),
    t("fpa.deadline_days", days=days),
    delta_color=color,
)
st.progress(progress_val)
