"""
shared/styles.py — Brand CSS + mobile-responsive styles for Alta Fácil Pro.
Call inject_styles() once per page (done automatically via render_sidebar).
"""

import streamlit as st

_BRAND_CSS = """
<style>
/* ─── Brand tokens ──────────────────────────────────────────────────── */
:root {
    --af-teal:       #0FA876;
    --af-teal-end:   #00C896;
    --af-dark:       #1A3D30;
    --af-bg:         #F0FDF8;
    --af-bg2:        #E6FAF3;
    --af-muted:      #6DB89A;
    --af-red:        #E94560;
    --af-yellow:     #FFC93C;
    --af-radius:     12px;
}

/* ─── Global tweaks ─────────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Inter', 'Arial', sans-serif;
}

/* Remove default Streamlit top padding */
.block-container {
    padding-top: 1.5rem !important;
}

/* Metric cards — subtle card look */
[data-testid="metric-container"] {
    background: #ffffff;
    border: 1px solid rgba(15, 168, 118, 0.2);
    border-radius: var(--af-radius);
    padding: 1rem 1.25rem;
    box-shadow: 0 2px 8px rgba(15, 168, 118, 0.08);
}

/* Primary button → teal gradient */
div.stButton > button[kind="primary"],
div.stFormSubmitButton > button[kind="primary"] {
    background: linear-gradient(135deg, #0FA876, #00C896) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: var(--af-radius) !important;
    font-weight: 700 !important;
    letter-spacing: 0.3px;
    box-shadow: 0 3px 12px rgba(15, 168, 118, 0.35);
    transition: transform 0.15s, box-shadow 0.15s;
}
div.stButton > button[kind="primary"]:hover,
div.stFormSubmitButton > button[kind="primary"]:hover {
    transform: translateY(-1px);
    box-shadow: 0 5px 18px rgba(15, 168, 118, 0.45) !important;
}

/* Secondary button */
div.stButton > button[kind="secondary"] {
    border: 1.5px solid #0FA876 !important;
    color: #0FA876 !important;
    border-radius: var(--af-radius) !important;
    background: transparent !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #E6FAF3 !important;
    border-right: 1px solid rgba(15, 168, 118, 0.15);
}
[data-testid="stSidebar"] [data-testid="metric-container"] {
    background: #F0FDF8;
    border: 1px solid rgba(15, 168, 118, 0.2);
}

/* Success / info / warning / error — teal-aware */
[data-testid="stAlert"][data-baseweb="notification"] {
    border-radius: var(--af-radius);
}

/* Divider */
hr {
    border-color: rgba(15, 168, 118, 0.2) !important;
}

/* Tab strip */
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #0FA876 !important;
    border-bottom-color: #0FA876 !important;
}

/* Dataframe — light header */
[data-testid="stDataFrame"] thead th {
    background: var(--af-bg2) !important;
    color: var(--af-dark) !important;
}

/* ─── MOBILE — stack columns below 640 px ────────────────────────────── */
@media (max-width: 640px) {
    /* Make 4-col KPI rows go 2×2 */
    [data-testid="stHorizontalBlock"] > [data-testid="column"] {
        min-width: calc(50% - 0.5rem) !important;
        flex: 0 0 calc(50% - 0.5rem) !important;
    }

    /* Reduce page padding on mobile */
    .block-container {
        padding: 0.75rem 0.75rem 2rem !important;
        max-width: 100% !important;
    }

    /* Full-width buttons on mobile */
    div.stButton > button,
    div.stFormSubmitButton > button {
        width: 100% !important;
    }

    /* Charts fill width */
    [data-testid="stPlotlyChart"] {
        width: 100% !important;
    }

    /* Collapse expanders on mobile */
    [data-testid="stExpander"] summary {
        font-size: 0.9rem !important;
    }
}

/* ─── SMALL MOBILE — full-width columns below 420 px ────────────────── */
@media (max-width: 420px) {
    [data-testid="stHorizontalBlock"] > [data-testid="column"] {
        min-width: 100% !important;
        flex: 0 0 100% !important;
    }

    /* Larger tap targets */
    div.stButton > button {
        min-height: 2.75rem !important;
        font-size: 0.95rem !important;
    }

    [data-testid="metric-container"] {
        padding: 0.75rem !important;
    }

    /* Metric value slightly smaller */
    [data-testid="metric-container"] [data-testid="stMetricValue"] {
        font-size: 1.4rem !important;
    }
}

/* ─── Scanner page — camera + upload mobile fixes ────────────────────── */
@media (max-width: 640px) {
    /* Camera input fills container */
    [data-testid="stCameraInput"] video,
    [data-testid="stCameraInput"] img {
        width: 100% !important;
        max-height: 300px;
        object-fit: cover;
    }

    /* Radio horizontal wraps on mobile */
    [data-testid="stRadio"] > div {
        flex-wrap: wrap !important;
        gap: 0.5rem;
    }
}

/* ─── Chatbot page ────────────────────────────────────────────────────── */
@media (max-width: 640px) {
    [data-testid="stChatInput"] {
        position: sticky !important;
        bottom: 0;
        background: var(--af-bg) !important;
        padding: 0.5rem 0 !important;
        z-index: 100;
    }
}

/* ─── Hide Streamlit default branding on mobile ──────────────────────── */
@media (max-width: 640px) {
    #MainMenu, footer, header[data-testid="stHeader"] {
        display: none !important;
    }
    /* But keep sidebar hamburger */
    [data-testid="collapsedControl"] {
        display: flex !important;
    }
}
</style>
"""


def inject_styles() -> None:
    """Inject brand + mobile-responsive CSS. Call once per page via render_sidebar."""
    st.markdown(_BRAND_CSS, unsafe_allow_html=True)
