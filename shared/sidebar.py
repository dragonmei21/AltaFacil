import streamlit as st

from i18n import render_lang_switcher, t


def render_sidebar(profile: dict, summary: dict) -> None:
    render_lang_switcher()

    with st.sidebar:
        name = (profile or {}).get("nombre", "")
        alta_date = (profile or {}).get("alta_date", "")

        st.markdown(f"### 🚀 {t('sidebar.greeting', name=name)}")
        if alta_date:
            st.caption(t("sidebar.since", date=alta_date))
        st.divider()

        total_ingresos = float((summary or {}).get("total_ingresos", 0.0))
        resultado_303 = float((summary or {}).get("resultado_303", 0.0))

        st.metric(t("sidebar.kpi_revenue"), f"€{total_ingresos:,.0f}")
        st.metric(t("sidebar.kpi_iva"), f"€{max(0, resultado_303):,.0f}")
        st.divider()

        if not st.session_state.get("gmail_connected"):
            if st.button(t("sidebar.connect_gmail"), use_container_width=True):
                st.session_state["gmail_connected"] = True
                st.rerun()
        else:
            st.success(t("sidebar.gmail_connected"))

        if not st.session_state.get("calendly_connected"):
            token = st.text_input(
                t("sidebar.calendly_token_placeholder"),
                type="password",
                key="calendly_input",
            )
            if token and st.button(t("sidebar.connect_calendly"), use_container_width=True):
                st.session_state["calendly_token"] = token
                st.session_state["calendly_connected"] = True
                st.rerun()
        else:
            st.success(t("sidebar.calendly_connected"))
