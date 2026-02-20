import json
import streamlit as st
from pathlib import Path

LANGS = ["es", "en"]
LANG_LABELS = {"es": "\u00f0\u009f\u0087\u00aa\u00f0\u009f\u0087\u00b8 Espa\u00f1ol", "en": "\u00f0\u009f\u0087\u00ac\u00f0\u009f\u0087\u00a7 English"}
DEFAULT_LANG = "es"

_cache: dict[str, dict] = {}


def _load(lang: str) -> dict:
    if lang not in _cache:
        path = Path(__file__).parent / f"{lang}.json"
        with open(path, encoding="utf-8") as f:
            _cache[lang] = json.load(f)
    return _cache[lang]


def get_lang() -> str:
    return st.session_state.get("lang", DEFAULT_LANG)


def set_lang(lang: str) -> None:
    assert lang in LANGS, f"Unsupported language: {lang}"
    st.session_state["lang"] = lang


def t(key: str, **kwargs) -> str:
    """
    Translate a key to the current language.

    Supports dot-notation keys: t("dashboard.title")
    Supports format substitutions: t("dashboard.greeting", name="María")
    Falls back to Spanish if key missing in English.
    Falls back to key itself if missing in both.
    """
    lang = get_lang()
    strings = _load(lang)

    keys = key.split(".")
    val = strings
    for k in keys:
        if isinstance(val, dict) and k in val:
            val = val[k]
        else:
            # Fallback to Spanish
            val = _load("es")
            for k2 in keys:
                if isinstance(val, dict) and k2 in val:
                    val = val[k2]
                else:
                    return key  # Last resort: return key itself
            break

    if not isinstance(val, str):
        return key

    return val.format(**kwargs) if kwargs else val


def tax_term(key: str):
    """
    Return (label, tooltip) for a Spanish tax term.
    In English mode, tooltip is populated. In Spanish, tooltip is None.
    """
    label = t(f"tax_terms.{key}")
    tooltip = t(f"tax_terms.{key}_tooltip")
    return label, tooltip if tooltip else None


def tax_header(key: str):
    """Render subheader for a tax term, with caption tooltip in English."""
    label, tooltip = tax_term(key)
    st.subheader(label)
    if tooltip:
        st.caption(f"\u2139\ufe0f {tooltip}")


def render_lang_switcher():
    """Render language toggle buttons in the sidebar. Call FIRST in every sidebar."""
    current = get_lang()
    col_es, col_en = st.sidebar.columns(2)

    with col_es:
        if st.button(
            "\U0001f1ea\U0001f1f8 ES",
            type="primary" if current == "es" else "secondary",
            use_container_width=True,
            key="lang_es",
        ):
            set_lang("es")
            st.rerun()

    with col_en:
        if st.button(
            "\U0001f1ec\U0001f1e7 EN",
            type="primary" if current == "en" else "secondary",
            use_container_width=True,
            key="lang_en",
        ):
            set_lang("en")
            st.rerun()

    st.sidebar.divider()


__all__ = [
    "t",
    "get_lang",
    "set_lang",
    "LANGS",
    "LANG_LABELS",
    "DEFAULT_LANG",
    "tax_term",
    "tax_header",
    "render_lang_switcher",
]
