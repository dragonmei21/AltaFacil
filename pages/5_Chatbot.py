import json

import streamlit as st

from engine.finance_engine import load_ledger, get_current_quarter, get_quarterly_summary
from engine.rag_retriever import index_ledger, index_tax_rules, retrieve_context
from engine.tax_rules import load_tax_rules
from i18n import t, get_lang
from shared.sidebar import render_sidebar


@st.cache_resource
def get_claude_client():
    """Create a single OpenAI client per session."""
    from openai import OpenAI
    import os

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


@st.cache_resource
def init_rag() -> bool:
    """
    Index ledger + tax rules into ChromaDB on first chatbot load.
    Cached with @st.cache_resource so it runs once per server process.
    New entries added via the Scanner are handled by index_entry() directly,
    so no re-indexing is needed when new invoices are scanned.
    Returns True if RAG is available, False if setup failed (app still works).
    """
    df = load_ledger()
    rules = load_tax_rules()
    ok_ledger = index_ledger(df)
    ok_rules = index_tax_rules(rules)
    return ok_ledger or ok_rules


def build_system_prompt(profile: dict, summary: dict) -> str:
    """Build the base system prompt with live user + aggregate ledger context."""
    lang = get_lang()
    language_instruction = (
        "Always respond in English." if lang == "en" else "Responde siempre en español."
    )

    return f"""Eres El Gestor, un asesor fiscal especializado en autónomos españoles.
Tienes acceso a los datos financieros reales del usuario para este trimestre.

PERFIL DEL USUARIO:
{json.dumps(profile, ensure_ascii=False, indent=2)}

RESUMEN FINANCIERO TRIMESTRE ACTUAL ({get_current_quarter()}):
- Ingresos totales: €{summary['total_ingresos']:,.2f}
- Gastos deducibles: €{summary['total_gastos_deducibles']:,.2f}
- IVA cobrado (repercutido): €{summary['iva_cobrado']:,.2f}
- IVA soportado deducible: €{summary['iva_soportado_deducible']:,.2f}
- Resultado Modelo 303: €{summary['resultado_303']:,.2f} ({'a pagar' if summary['resultado_303'] > 0 else 'a compensar'})
- Beneficio neto estimado: €{summary['beneficio_neto']:,.2f}
- Provisión IRPF estimada: €{summary['irpf_provision']:,.2f}

INSTRUCCIONES:
- {language_instruction}
- Sé claro y directo, evita jerga innecesaria.
- Si faltan datos, dilo explícitamente y pide lo mínimo necesario.
- Cuando cites artículos legales, menciona la ley completa (e.g. "Art. 90.Uno Ley 37/1992").
- SIEMPRE añade al final: "Para declaraciones oficiales, consulta siempre con tu gestor."
"""


profile = st.session_state.get("user_profile", {})
df = load_ledger()
quarter = get_current_quarter()
summary = get_quarterly_summary(df, quarter)

render_sidebar(profile, summary)

st.title(t("chatbot.title"))
st.info(t("chatbot.disclaimer"))

client = get_claude_client()
system_prompt = build_system_prompt(profile, summary)

# Initialise vector store once per session (non-blocking — fails silently).
rag_available = init_rag()

# Suggestion buttons when chat is empty.
if not st.session_state.get("messages"):
    st.caption(t("chatbot.suggestions_label"))
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button(t("chatbot.suggestion_1"), key="sugg_0"):
            st.session_state.setdefault("messages", []).append(
                {"role": "user", "content": t("chatbot.suggestion_1")}
            )
    with col2:
        if st.button(t("chatbot.suggestion_2"), key="sugg_1"):
            st.session_state.setdefault("messages", []).append(
                {"role": "user", "content": t("chatbot.suggestion_2")}
            )
    with col3:
        if st.button(t("chatbot.suggestion_3"), key="sugg_2"):
            st.session_state.setdefault("messages", []).append(
                {"role": "user", "content": t("chatbot.suggestion_3")}
            )

# Render chat history.
for msg in st.session_state.get("messages", []):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Input box for new user message.
prompt = st.chat_input(t("chatbot.placeholder"))
if prompt:
    st.session_state.setdefault("messages", []).append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner(t("chatbot.spinner")):
            if not client:
                reply = t("chatbot.error_no_api_key")
            else:
                # Retrieve semantically relevant ledger entries + tax rules for
                # this specific query and inject them into the system prompt.
                # Falls back to empty string if ChromaDB is unavailable.
                retrieved = retrieve_context(prompt) if rag_available else ""
                active_system_prompt = (
                    system_prompt + f"\n\n{retrieved}" if retrieved else system_prompt
                )

                messages = st.session_state.get("messages", [])
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": active_system_prompt},
                        *[
                            {"role": m["role"], "content": m["content"]}
                            for m in messages
                        ],
                    ],
                    max_tokens=1000,
                )
                reply = response.choices[0].message.content

            st.markdown(reply)
            st.session_state.setdefault("messages", []).append({"role": "assistant", "content": reply})
