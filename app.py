import json
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="Alta Fácil Pro",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="auto",  # collapsed on mobile, expanded on desktop
)


def init_session_state() -> None:
    defaults = {
        "lang": "es",
        "messages": [],
        "last_gmail_check": None,
        "gmail_connected": False,
        "calendly_connected": False,
        "calendly_token": None,
        "processed_document": None,
        "invoice_draft": None,
        "user_profile": None,
        "ledger_cache_key": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()

profile_path = Path("data/user_profile.json")
if not profile_path.exists():
    st.switch_page("pages/0_Onboarding.py")
else:
    with open(profile_path, encoding="utf-8") as f:
        profile = json.load(f)

    if not profile.get("onboarding_complete"):
        st.switch_page("pages/0_Onboarding.py")
    else:
        st.session_state["user_profile"] = profile
        st.switch_page("pages/1_Dashboard.py")
