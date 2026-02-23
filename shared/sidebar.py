import base64
from pathlib import Path

import streamlit as st

from i18n import render_lang_switcher, t
from shared.styles import inject_styles


def _logo_html() -> str:
    """Return an <img> tag with the SVG logo encoded as base64."""
    logo_path = Path("altafacil_logo_teal.svg")
    if logo_path.exists():
        data = base64.b64encode(logo_path.read_bytes()).decode()
        return (
            f'<img src="data:image/svg+xml;base64,{data}" '
            f'style="width:100%;max-width:240px;display:block;margin:0 auto 0.5rem;" '
            f'alt="Alta Fácil Pro"/>'
        )
    # Fallback text logo if file missing
    return (
        '<p style="font-size:1.4rem;font-weight:900;color:#0FA876;'
        'letter-spacing:-1px;margin:0;">ALTA<br>'
        '<span style="color:#1A3D30;">FÁCIL</span></p>'
    )


def render_sidebar(profile: dict, summary: dict) -> None:
    # Inject brand + mobile CSS on every page
    inject_styles()

    render_lang_switcher()

    with st.sidebar:
        # Logo
        st.markdown(_logo_html(), unsafe_allow_html=True)
        st.divider()

        name = (profile or {}).get("nombre", "")
        alta_date = (profile or {}).get("alta_date", "")

        if name:
            st.markdown(
                f"<p style='font-size:1rem;font-weight:700;color:#1A3D30;margin:0'>"
                f"👤 {t('sidebar.greeting', name=name)}</p>",
                unsafe_allow_html=True,
            )
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
