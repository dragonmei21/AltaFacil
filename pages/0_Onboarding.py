import json
from pathlib import Path

import streamlit as st

from i18n import t
from shared.sidebar import render_sidebar


def _map_iva_regime(label: str) -> str:
    mapping = {
        t("onboarding.iva_general"): "general",
        t("onboarding.iva_simplificado"): "simplificado",
        t("onboarding.iva_exento"): "exento",
    }
    return mapping.get(label, "general")


def _map_work_location(label: str) -> str:
    mapping = {
        t("onboarding.location_casa"): "casa",
        t("onboarding.location_oficina"): "oficina",
        t("onboarding.location_mixto"): "mixto",
    }
    return mapping.get(label, "oficina")


render_sidebar({}, {"total_ingresos": 0.0, "resultado_303": 0.0})

st.title(f"🚀 {t('onboarding.title')}")
st.subheader(t("onboarding.subtitle"))

with st.form("onboarding_form"):
    nombre = st.text_input(
        t("onboarding.field_name"),
        placeholder=t("onboarding.field_name_placeholder"),
    )

    actividad = st.text_input(
        t("onboarding.field_actividad"),
        placeholder=t("onboarding.field_actividad_placeholder"),
    )

    iva_regime_label = st.radio(
        t("onboarding.field_iva_regime"),
        options=[
            t("onboarding.iva_general"),
            t("onboarding.iva_simplificado"),
            t("onboarding.iva_exento"),
        ],
        index=0,
        help=t("onboarding.field_iva_regime_help"),
    )

    work_location_label = st.radio(
        t("onboarding.field_work_location"),
        options=[
            t("onboarding.location_casa"),
            t("onboarding.location_oficina"),
            t("onboarding.location_mixto"),
        ],
        horizontal=True,
    )

    home_office_pct = 0
    if work_location_label != t("onboarding.location_oficina"):
        home_office_pct = st.slider(
            t("onboarding.field_home_pct"),
            min_value=5,
            max_value=50,
            value=30,
            step=5,
            help=t("onboarding.field_home_pct_help"),
        )

    tarifa_plana = st.checkbox(
        t("onboarding.field_tarifa_plana"),
        value=True,
    )

    alta_date = st.date_input(
        t("onboarding.field_alta_date"),
        help=t("onboarding.field_alta_date_help"),
    )

    irpf_retencion = st.select_slider(
        t("onboarding.field_irpf"),
        options=[0, 7, 15, 19],
        value=15,
        help=t("onboarding.field_irpf_help"),
    )

    submitted = st.form_submit_button(t("onboarding.btn_submit"), type="primary")

if submitted:
    has_error = False
    if not nombre.strip():
        st.error(t("onboarding.error_name_required"))
        has_error = True
    if not actividad.strip():
        st.error(t("onboarding.error_actividad_required"))
        has_error = True
    if has_error:
        st.stop()

    profile = {
        "nombre": nombre.strip(),
        "actividad": actividad.strip(),
        "iae_code": "",
        "iva_regime": _map_iva_regime(iva_regime_label),
        "irpf_retencion_pct": int(irpf_retencion),
        "work_location": _map_work_location(work_location_label),
        "home_office_pct": int(home_office_pct),
        "ss_bracket_monthly": 200,
        "tarifa_plana": bool(tarifa_plana),
        "tarifa_plana_end_date": None,
        "alta_date": alta_date.isoformat(),
        "autonomia": "peninsular",
        "onboarding_complete": True,
    }

    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    profile_path = data_dir / "user_profile.json"
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    st.session_state["user_profile"] = profile
    st.switch_page("pages/1_Dashboard.py")
