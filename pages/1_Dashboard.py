import os
from datetime import datetime, timedelta

import streamlit as st
import plotly.graph_objects as go

from engine.finance_engine import (
    load_ledger,
    get_current_quarter,
    get_quarterly_summary,
    get_monthly_breakdown,
    save_to_ledger,
)
from engine.gmail_watcher import check_new_invoices
from engine.tax_rules import load_tax_rules
from i18n import t
from shared.sidebar import render_sidebar


@st.cache_data(ttl=30)
def cached_ledger(cache_key: int):
    """Load ledger with caching; cache_key forces refresh after writes."""
    return load_ledger()


@st.cache_resource
def get_claude_client():
    """Create a single OpenAI client per session (for Gmail invoice parsing)."""
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def should_poll_gmail(last_check: str | None) -> bool:
    """Return True if Gmail was checked 15+ minutes ago or never."""
    if not last_check:
        return True
    try:
        last_dt = datetime.fromisoformat(last_check)
    except ValueError:
        return True
    return datetime.now() - last_dt >= timedelta(minutes=15)


def previous_quarter(q: str) -> str:
    """Convert 'YYYY-QN' to previous quarter string."""
    year, qtr = q.split("-Q")
    year = int(year)
    qtr = int(qtr)
    if qtr == 1:
        return f"{year - 1}-Q4"
    return f"{year}-Q{qtr - 1}"


profile = st.session_state.get("user_profile", {})
ledger_key = st.session_state.get("ledger_cache_key", 0)
df = cached_ledger(ledger_key)

quarter = get_current_quarter()
summary = get_quarterly_summary(df, quarter)

render_sidebar(profile, summary)

st.title(t("dashboard.title", name=profile.get("nombre", "").split(" ")[0] if profile else ""))
st.caption(t("dashboard.subtitle", quarter=quarter))

# KPI row
prev_summary = get_quarterly_summary(df, previous_quarter(quarter))
delta_ingresos = summary["total_ingresos"] - prev_summary["total_ingresos"]

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(
        label=t("dashboard.kpi_revenue_label"),
        value=f"€{summary['total_ingresos']:,.0f}",
        delta=f"+€{delta_ingresos:,.0f}",
    )
with col2:
    st.metric(
        label=t("dashboard.kpi_expenses_label"),
        value=f"€{summary['total_gastos_deducibles']:,.0f}",
    )
with col3:
    st.metric(
        label=t("dashboard.kpi_iva_label"),
        value=f"€{max(0, summary['resultado_303']):,.0f}",
        delta="Modelo 303",
        delta_color="off",
    )
with col4:
    st.metric(
        label=t("dashboard.kpi_irpf_label"),
        value=f"€{summary['irpf_provision']:,.0f}",
        delta=t("dashboard.kpi_irpf_delta"),
        delta_color="off",
    )

# Monthly cashflow chart
monthly = get_monthly_breakdown(df, datetime.now().year)
fig = go.Figure()
fig.add_bar(
    name=t("dashboard.chart_ingresos"),
    x=monthly["month"],
    y=monthly["ingresos"],
    marker_color="#00D9A5",
)
fig.add_bar(
    name=t("dashboard.chart_gastos"),
    x=monthly["month"],
    y=monthly["gastos_base"],
    marker_color="#E94560",
)
fig.add_bar(
    name=t("dashboard.chart_provision"),
    x=monthly["month"],
    y=monthly["tax_provision"],
    marker_color="#FFC93C",
)
fig.update_layout(
    barmode="group",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#EDF2F4",
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    height=350,
    title=t("dashboard.chart_title"),
)
st.plotly_chart(fig, use_container_width=True)

# Recent transactions table
st.subheader(t("dashboard.recent_title"))
recent = df.tail(10).sort_values("fecha", ascending=False)


def color_row(row):
    """Apply row color based on type/deductibility."""
    if row["tipo"] == "ingreso":
        return ["background-color: rgba(0,217,165,0.1)"] * len(row)
    if row["deducible"]:
        return ["background-color: rgba(233,69,96,0.1)"] * len(row)
    return ["background-color: rgba(255,201,60,0.1)"] * len(row)


styled = recent[
    ["fecha", "tipo", "proveedor_cliente", "concepto", "total", "deducible", "estado"]
].style.apply(color_row, axis=1)
st.dataframe(styled, use_container_width=True, hide_index=True)

# Gmail polling + toasts
if st.session_state.get("gmail_connected") and should_poll_gmail(
    st.session_state.get("last_gmail_check")
):
    tax_rules = load_tax_rules()
    claude_client = get_claude_client()
    creds_path = os.getenv("GMAIL_CREDENTIALS_PATH", "")

    new_invoices = check_new_invoices(
        credentials_path=creds_path,
        last_check_timestamp=st.session_state.get("last_gmail_check") or "",
        user_profile=profile,
        tax_rules=tax_rules,
        claude_client=claude_client,
    )

    if new_invoices:
        for inv in new_invoices:
            save_to_ledger(inv)
            st.toast(
                t("dashboard.toast_new_invoice", proveedor=inv["proveedor"], total=inv["total"]),
                icon="📧",
            )
        st.cache_data.clear()

    st.session_state["last_gmail_check"] = datetime.now().isoformat()
