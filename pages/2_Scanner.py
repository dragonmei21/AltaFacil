from datetime import date

import streamlit as st

from engine.finance_engine import load_ledger, save_to_ledger
from engine.invoice_parser import process_document
from engine.tax_rules import load_tax_rules, classify_deductibility
from i18n import t
from shared.sidebar import render_sidebar


@st.cache_data
def cached_tax_rules():
    """Load tax rules once; this file is static."""
    return load_tax_rules()


@st.cache_resource
def get_claude_client():
    """Create a single OpenAI client per session."""
    from openai import OpenAI
    import os

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def build_ledger_entry(result: dict, origen: str, tipo: str) -> dict:
    """Map a processed result into ledger schema fields."""
    base = float(result.get("base_imponible", 0.0))
    tipo_iva = int(result.get("tipo_iva", 21))
    cuota_iva = round(base * tipo_iva / 100, 2)
    total = round(base + cuota_iva, 2)
    return {
        "fecha": result.get("fecha", ""),
        "tipo": tipo,
        "proveedor_cliente": result.get("proveedor", ""),
        "nif": result.get("nif_proveedor") or "",
        "concepto": result.get("concepto", ""),
        "numero_factura": result.get("numero_factura") or "",
        "base_imponible": base,
        "tipo_iva": tipo_iva,
        "cuota_iva": cuota_iva,
        "total": total,
        "deducible": bool(result.get("deducible", False)),
        "porcentaje_deduccion": int(result.get("porcentaje_deduccion", 0)),
        "cuota_iva_deducible": float(result.get("cuota_iva_deducible", 0.0)),
        "aeat_articulo": result.get("deductibility_article") or result.get("iva_article", ""),
        "estado": "pendiente",
        "origen": origen,
    }


def classify_manual_entry(
    proveedor: str,
    fecha: str,
    concepto: str,
    numero: str,
    base: float,
    tipo_iva: int,
    user_profile: dict,
    tax_rules: dict,
) -> dict:
    """Build a result dict from manual input (no OCR)."""
    cuota_iva = round(base * tipo_iva / 100, 2)
    total = round(base + cuota_iva, 2)

    iva_rate = tax_rules["iva_rates"][str(tipo_iva)]
    exempt = tipo_iva == 0
    ded = classify_deductibility(concepto, tipo_iva, exempt, user_profile, tax_rules)
    ded["cuota_iva_deducible"] = round(cuota_iva * ded["porcentaje_deduccion"] / 100, 2)

    return {
        "proveedor": proveedor,
        "nif_proveedor": None,
        "fecha": fecha,
        "numero_factura": numero or None,
        "base_imponible": base,
        "tipo_iva": tipo_iva,
        "cuota_iva": cuota_iva,
        "total": total,
        "concepto": concepto,
        "tipo_documento": "factura",
        "iva_label": iva_rate["label"],
        "iva_article": iva_rate["article"],
        "iva_confidence": "high",
        "exempt": exempt,
        "deducible": ded["deducible"],
        "porcentaje_deduccion": ded["porcentaje_deduccion"],
        "cuota_iva_deducible": ded["cuota_iva_deducible"],
        "deductibility_justification": ded["justification"],
        "deductibility_article": ded["article"],
        "extraction_method": "manual",
        "parse_error": False,
        "iva_discrepancy": False,
    }


# --- Page setup ---
profile = st.session_state.get("user_profile", {})
render_sidebar(profile, {"total_ingresos": 0.0, "resultado_303": 0.0})

st.title(f"🔍 {t('scanner.title')}")
st.caption(t("scanner.subtitle"))

# Core dependencies for this page.
tax_rules = cached_tax_rules()
claude_client = get_claude_client()

methods = [
    t("scanner.method_upload"),
    t("scanner.method_camera"),
    t("scanner.method_manual"),
]

draft = st.session_state.get("invoice_draft")
default_index = 2 if draft else 0

# --- Input method selector ---
method = st.radio(
    t("scanner.title"),
    options=methods,
    horizontal=True,
    label_visibility="collapsed",
    index=default_index,
)

uploaded_file = None
camera_image = None
submit_manual = False

if method == t("scanner.method_upload"):
    uploaded_file = st.file_uploader(
        t("scanner.upload_label"),
        type=["pdf", "jpg", "jpeg", "png", "heic"],
        label_visibility="collapsed",
    )
    if uploaded_file and uploaded_file.type.startswith("image"):
        st.image(uploaded_file, width=400)

elif method == t("scanner.method_camera"):
    camera_image = st.camera_input(t("scanner.camera_label"))

elif method == t("scanner.method_manual"):
    # Manual form captures inputs and shows a preview (IVA/total) before classification.
    with st.form("manual_entry"):
        col1, col2 = st.columns(2)
        with col1:
            m_proveedor = st.text_input(
                t("scanner.manual_proveedor"),
                value=(draft.get("proveedor_cliente") if draft else ""),
            )
            m_fecha = st.date_input(
                t("scanner.manual_fecha"),
                value=(
                    date.fromisoformat(draft["fecha"])
                    if draft and draft.get("fecha")
                    else date.today()
                ),
            )
            m_concepto = st.text_input(
                t("scanner.manual_concepto"),
                placeholder=t("scanner.manual_concepto_placeholder"),
                value=(draft.get("concepto") if draft else ""),
            )
            m_numero = st.text_input(
                t("scanner.manual_numero"),
                value=(draft.get("numero_factura") if draft else ""),
            )
        with col2:
            m_base = st.number_input(
                t("scanner.manual_base"),
                min_value=0.01,
                step=0.01,
                value=float(draft.get("base_imponible", 0.01)) if draft else 0.01,
            )
            m_tipo_iva = st.selectbox(
                t("scanner.manual_tipo_iva"),
                options=[21, 10, 4, 0],
                index=[21, 10, 4, 0].index(int(draft.get("tipo_iva", 21))) if draft else 0,
            )
            m_cuota = m_base * m_tipo_iva / 100
            st.metric(t("scanner.manual_cuota_calculated"), f"€{m_cuota:.2f}")
            m_total = m_base + m_cuota
            st.metric(t("scanner.manual_total"), f"€{m_total:.2f}")
        submit_manual = st.form_submit_button(
            t("scanner.manual_btn_submit"),
            type="primary",
        )

    if submit_manual:
        # Build a synthetic "result" dict so the rest of the UI can stay the same.
        result = classify_manual_entry(
            m_proveedor.strip(),
            m_fecha.isoformat(),
            m_concepto.strip(),
            m_numero.strip(),
            float(m_base),
            int(m_tipo_iva),
            profile,
            tax_rules,
        )
        result["origen"] = "manual"
        result["tipo"] = draft.get("tipo", "gasto") if draft else "gasto"
        st.session_state["processed_document"] = result

file_ready = uploaded_file is not None or camera_image is not None
if file_ready and st.button(t("scanner.btn_analyze"), type="primary", use_container_width=True):
    try:
        with st.spinner(t("scanner.spinner_analyzing")):
            file_bytes = uploaded_file.read() if uploaded_file else camera_image.getvalue()
            file_type = (
                "pdf" if (uploaded_file and uploaded_file.type == "application/pdf") else "image"
            )
            result = process_document(
                file_bytes,
                file_type,
                profile,
                tax_rules,
                claude_client,
            )
            result["origen"] = "scanner"
            result["tipo"] = "gasto"
            st.session_state["processed_document"] = result
    except ValueError as e:
        st.error(t("scanner.error_ocr_failed", error=str(e)))
        st.caption(t("scanner.error_ocr_hint"))

if st.session_state.get("processed_document"):
    result = st.session_state.get("processed_document")

    # --- Results area (3-column layout) ---
    st.divider()
    st.subheader(t("scanner.results_title"))

    if result.get("iva_discrepancy"):
        st.warning(
            t(
                "scanner.iva_discrepancy",
                extracted=result.get("cuota_iva", 0.0),
                calculated=result.get("cuota_iva", 0.0),
            )
        )

    col_extract, col_verdict, col_edit = st.columns([1, 1, 1])

    with col_extract:
        # Extracted fields summary.
        st.subheader(t("scanner.col_extracted"))
        st.metric(t("scanner.metric_proveedor"), result.get("proveedor", ""))
        st.metric(t("scanner.metric_fecha"), result.get("fecha", ""))
        st.metric(t("scanner.metric_base"), f"€{result.get('base_imponible', 0.0):.2f}")
        st.metric(
            t("scanner.metric_iva"),
            f"{result.get('tipo_iva', 21)}% → €{result.get('cuota_iva', 0.0):.2f}",
        )
        st.metric(t("scanner.metric_total"), f"€{result.get('total', 0.0):.2f}")

    with col_verdict:
        # Fiscal classification + deductibility.
        st.subheader(t("scanner.col_verdict"))
        st.info(
            t(
                "scanner.verdict_iva_label",
                pct=result.get("tipo_iva", 21),
                label=result.get("iva_label", ""),
            )
            + f"\n\n{result.get('iva_article', '')}"
        )

        pct = result.get("porcentaje_deduccion", 0)
        if pct == 100:
            st.success(
                t(
                    "scanner.verdict_deducible_100",
                    amount=f"{result.get('cuota_iva_deducible', 0.0):.2f}",
                )
            )
        elif pct > 0:
            st.warning(
                t(
                    "scanner.verdict_deducible_partial",
                    pct=pct,
                    deducible=f"{result.get('cuota_iva_deducible', 0.0):.2f}",
                    total=f"{result.get('cuota_iva', 0.0):.2f}",
                )
            )
        else:
            st.error(t("scanner.verdict_no_deducible"))

        st.caption(t("tax_verdicts.disclaimer_tax"))

    with col_edit:
        # Edit panel to correct extraction and re-run classification.
        st.subheader(t("scanner.col_edit"))
        with st.expander(t("scanner.edit_expander"), expanded=False):
            r_proveedor = st.text_input(
                t("scanner.edit_proveedor"),
                value=result.get("proveedor", ""),
                key="r_prov",
            )
            r_fecha = st.text_input(
                t("scanner.edit_fecha"),
                value=result.get("fecha", ""),
                key="r_fecha",
            )
            r_base = st.number_input(
                t("scanner.edit_base"),
                value=float(result.get("base_imponible", 0.0)),
                key="r_base",
            )
            r_iva = st.selectbox(
                t("scanner.edit_iva"),
                [21, 10, 4, 0],
                index=[21, 10, 4, 0].index(int(result.get("tipo_iva", 21))),
                key="r_iva",
            )
            r_concepto = st.text_input(
                t("scanner.edit_concepto"),
                value=result.get("concepto", ""),
                key="r_conc",
            )
            if st.button(t("scanner.btn_apply_edits")):
                # Recompute IVA + deductibility after edits.
                iva_rate = tax_rules["iva_rates"][str(r_iva)]
                exempt = r_iva == 0
                ded = classify_deductibility(
                    r_concepto, r_iva, exempt, profile, tax_rules
                )
                cuota_iva = round(float(r_base) * int(r_iva) / 100, 2)
                updated = {
                    **result,
                    "proveedor": r_proveedor,
                    "fecha": r_fecha,
                    "base_imponible": float(r_base),
                    "tipo_iva": int(r_iva),
                    "cuota_iva": cuota_iva,
                    "total": round(float(r_base) + cuota_iva, 2),
                    "concepto": r_concepto,
                    "iva_label": iva_rate["label"],
                    "iva_article": iva_rate["article"],
                    "iva_confidence": "high",
                    "exempt": exempt,
                    "deducible": ded["deducible"],
                    "porcentaje_deduccion": ded["porcentaje_deduccion"],
                    "cuota_iva_deducible": round(
                        cuota_iva * ded["porcentaje_deduccion"] / 100, 2
                    ),
                    "deductibility_justification": ded["justification"],
                    "deductibility_article": ded["article"],
                }
                st.session_state["processed_document"] = updated
                st.rerun()

    st.divider()
    if st.button(t("scanner.btn_save"), type="primary", use_container_width=True):
        # Persist the entry into the ledger CSV.
        entry = build_ledger_entry(
            result,
            origen=result.get("origen", "scanner"),
            tipo=result.get("tipo", "gasto"),
        )
        save_to_ledger(entry)
        st.cache_data.clear()
        st.balloons()
        st.success(
            t(
                "scanner.save_success",
                proveedor=result.get("proveedor", ""),
                amount=f"{result.get('cuota_iva_deducible', 0.0):.2f}",
            )
        )
        st.session_state["processed_document"] = None
        st.session_state["invoice_draft"] = None

# --- Recent entries table ---
st.divider()
st.subheader(t("scanner.recent_title"))
df = load_ledger()
gastos = df[df["tipo"] == "gasto"].tail(10).sort_values("fecha", ascending=False)


def color_deducible(val):
    """Color rows by deductibility."""
    if val is True:
        return "background-color: rgba(0,217,165,0.15)"
    return "background-color: rgba(233,69,96,0.15)"


styled = gastos[
    [
        "fecha",
        "proveedor_cliente",
        "concepto",
        "total",
        "tipo_iva",
        "porcentaje_deduccion",
        "cuota_iva_deducible",
        "deducible",
    ]
].style.applymap(color_deducible, subset=["deducible"])
st.dataframe(styled, use_container_width=True, hide_index=True)
