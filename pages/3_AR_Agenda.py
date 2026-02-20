import pandas as pd
import streamlit as st

from engine.calendly_client import generate_invoice_draft, get_scheduled_events, get_user_uri
from engine.finance_engine import (
    get_ar_aging,
    get_current_quarter,
    get_quarterly_summary,
    load_ledger,
)
from i18n import t
from shared.sidebar import render_sidebar


profile = st.session_state.get("user_profile", {})
df = load_ledger()
summary = get_quarterly_summary(df, get_current_quarter())
render_sidebar(profile, summary)

st.title(t("agenda.title"))

tab_upcoming, tab_invoices, tab_aging = st.tabs(
    [t("agenda.tab_upcoming"), t("agenda.tab_invoices"), t("agenda.tab_aging")]
)

with tab_upcoming:
    if not st.session_state.get("calendly_connected"):
        st.info(t("agenda.no_calendly"))
        st.caption(t("agenda.no_calendly_hint"))
    else:
        token = st.session_state.get("calendly_token", "")
        user_uri = st.session_state.get("calendly_user_uri", "")

        try:
            if token and not user_uri:
                user_uri = get_user_uri(token)
                st.session_state["calendly_user_uri"] = user_uri

            events = get_scheduled_events(token, user_uri)
        except Exception as exc:
            st.error(t("common.error_api", error=str(exc)))
            events = []

        df_events = pd.DataFrame(events)
        st.dataframe(df_events, use_container_width=True, hide_index=True)

        completed = [event for event in events if event.get("estado") == "completado"]
        for event in completed:
            col_info, col_btn = st.columns([3, 1])
            with col_info:
                st.write(
                    t(
                        "agenda.event_line",
                        event=event.get("nombre_evento", ""),
                        client=event.get("cliente_nombre", ""),
                        date=event.get("fecha_inicio", "")[:10],
                    )
                )
            with col_btn:
                if st.button(t("agenda.btn_generate_invoice"), key=f"inv_{event.get('event_uuid', '')}"):
                    draft = generate_invoice_draft(event, profile)
                    st.session_state["invoice_draft"] = draft
                    st.switch_page("pages/2_Scanner.py")

with tab_invoices:
    ingresos = df[df["tipo"] == "ingreso"].sort_values("fecha", ascending=False)
    st.metric(t("agenda.metric_total_invoiced"), f"€{ingresos['total'].sum():,.2f}")
    st.metric(
        t("agenda.metric_pending"),
        f"€{ingresos[ingresos['estado'] == 'pendiente']['total'].sum():,.2f}",
    )
    st.dataframe(
        ingresos[["fecha", "proveedor_cliente", "concepto", "total", "estado"]],
        use_container_width=True,
        hide_index=True,
    )

with tab_aging:
    st.subheader(t("agenda.aging_title"))
    aging_df = get_ar_aging(df)

    def color_aging(val: str) -> str:
        colors = {"0-30": "#00D9A5", "31-60": "#FFC93C", "61-90": "#FF8C00", "90+": "#E94560"}
        return f"color: {colors.get(val, 'white')}"

    if aging_df.empty:
        st.dataframe(aging_df, use_container_width=True, hide_index=True)
    else:
        styled = aging_df.style.applymap(color_aging, subset=["aging_bucket"])
        st.dataframe(styled, use_container_width=True, hide_index=True)
