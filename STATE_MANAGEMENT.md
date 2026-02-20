# STATE_MANAGEMENT.md — Alta Fácil Pro

> **What this document is:** The complete map of application state. What lives in `st.session_state`, what is cached, what is persisted to disk, and what is intentionally ephemeral. Read this before adding any new state to the app — ghost bugs in Streamlit almost always come from unplanned state.

---

## 1. The Three State Tiers

```
TIER 1 — PERSISTENT (survives app restart)
  data/ledger.csv          — all financial entries
  data/user_profile.json   — onboarding answers

TIER 2 — SESSION (survives page navigation, dies when tab closes)
  st.session_state         — all keys documented in Section 2

TIER 3 — CACHED (survives reruns, invalidated by TTL or explicit .clear())
  @st.cache_data           — loaded DataFrames and dicts
  @st.cache_resource       — single Anthropic client instance
```

**Rule:** Never promote Tier 3 data to Tier 2 manually. Use the cache layer. Never promote Tier 2 data to Tier 1 unless the user explicitly triggers a save action.

---

## 2. Complete `st.session_state` Key Registry

Every key that is ever set in `st.session_state` must appear in this table. If you add a new key, add it here first.

### 2.1 Initialised in `app.py → init_session_state()`

All keys below are set with defaults in `init_session_state()`. This function runs on every cold start. It uses the pattern `if key not in st.session_state: st.session_state[key] = default` — existing values are never overwritten.

| Key | Type | Default | Set By | Read By | Purpose |
|---|---|---|---|---|---|
| `lang` | `str` | `"es"` | `app.py`, `i18n.set_lang()` | `i18n.get_lang()`, every page | Active UI language |
| `messages` | `list[dict]` | `[]` | `pages/5_Chatbot.py` | `pages/5_Chatbot.py` | Chat history `[{"role": str, "content": str}]` |
| `last_gmail_check` | `str \| None` | `None` | `pages/1_Dashboard.py` | `pages/1_Dashboard.py` | ISO datetime of last Gmail poll |
| `gmail_connected` | `bool` | `False` | `render_sidebar()` | `pages/1_Dashboard.py`, sidebar | Gmail OAuth state |
| `calendly_connected` | `bool` | `False` | `render_sidebar()` | `pages/3_AR_Agenda.py`, sidebar | Calendly connection state |
| `calendly_token` | `str \| None` | `None` | `render_sidebar()` | `engine/calendly_client.py` calls | Calendly access token |
| `processed_document` | `dict \| None` | `None` | `pages/2_Scanner.py` | `pages/2_Scanner.py` | Last invoice extraction result |
| `invoice_draft` | `dict \| None` | `None` | `pages/3_AR_Agenda.py` | `pages/2_Scanner.py` | Pre-filled draft from Calendly |
| `user_profile` | `dict \| None` | `None` | `app.py`, `pages/0_Onboarding.py` | Every page, engine calls | Loaded user_profile.json |
| `ledger_cache_key` | `int` | `0` | `engine/finance_engine.py` | `@st.cache_data` key param | Forces cache invalidation after save |

### 2.2 Widget State (Managed Automatically by Streamlit)

These are NOT manually set — Streamlit manages them internally when you use `key=` on widgets. Never read or set these manually.

| Widget | Auto Key | Notes |
|---|---|---|
| Language buttons | `"lang_es"`, `"lang_en"` | Sidebar buttons |
| Suggestion buttons | `"sugg_0"`, `"sugg_1"`, `"sugg_2"` | Chatbot page |
| Calendly token input | `"calendly_input"` | Sidebar text_input |
| Edit form fields | `"r_prov"`, `"r_fecha"`, `"r_base"`, `"r_iva"`, `"r_conc"` | Scanner edit expander |
| Generate invoice buttons | `"inv_{event_uuid}"` | AR Agenda tab |

---

## 3. State Lifecycle Diagrams

### 3.1 `processed_document` Lifecycle

```
SET:   pages/2_Scanner.py — after process_document() returns
       st.session_state["processed_document"] = result_dict

READ:  pages/2_Scanner.py — to display extraction results
       if st.session_state.get("processed_document"):
           result = st.session_state["processed_document"]
           # render results...

MUTATED: pages/2_Scanner.py — when user clicks "Apply corrections"
         st.session_state["processed_document"]["proveedor"] = new_value
         # re-run classify_iva() and classify_deductibility()
         # update result in session_state

CLEARED: pages/2_Scanner.py — immediately after successful save_to_ledger()
         st.session_state["processed_document"] = None

NEVER:
  - Persisted to disk
  - Passed to engine functions (pass individual fields instead)
  - Read by any page other than 2_Scanner.py
```

### 3.2 `messages` Lifecycle

```
SET INITIAL: app.py → init_session_state()
  st.session_state["messages"] = []

APPENDED: pages/5_Chatbot.py — on every user/assistant exchange
  st.session_state["messages"].append({"role": "user", "content": prompt})
  st.session_state["messages"].append({"role": "assistant", "content": reply})

READ: pages/5_Chatbot.py — to render chat history
  for msg in st.session_state["messages"]:
      with st.chat_message(msg["role"]):
          st.markdown(msg["content"])

ALSO SENT AS: Anthropic API messages array on every chat call

CLEARED: Never explicitly (dies when session ends)
         Optional: add "Clear conversation" button → st.session_state["messages"] = []

NEVER:
  - Persisted to disk
  - Read by any other page
  - Grows larger than ~20 messages before context window becomes expensive
    (Add warning or auto-trim if len(messages) > 20)
```

### 3.3 `user_profile` Lifecycle

```
SET: app.py on startup
  with open("data/user_profile.json") as f:
      st.session_state["user_profile"] = json.load(f)

SET: pages/0_Onboarding.py on form submit
  json.dump(profile, open("data/user_profile.json", "w"))
  st.session_state["user_profile"] = profile

READ: Every page — via st.session_state.get("user_profile", {})
      Engine calls — passed as argument to classify_deductibility(), build_system_prompt()

NEVER MUTATED after onboarding (no settings page in v1)
IF MISSING (file deleted): app.py redirects to onboarding
```

### 3.4 `lang` Lifecycle

```
SET INITIAL: app.py → init_session_state()
  st.session_state["lang"] = "es"

CHANGED: render_lang_switcher() in sidebar
  if st.button("🇬🇧 EN", key="lang_en"):
      set_lang("en")  # sets st.session_state["lang"] = "en"
      st.rerun()

READ: i18n.get_lang() — called inside t() on every string lookup

EFFECT OF CHANGE:
  st.rerun() fires → entire page re-renders → all t() calls return English strings
  Chatbot system prompt rebuilt with "Always respond in English"
  Tax term tooltips: non-empty strings render, empty strings render nothing

NEVER:
  - Persisted to disk (user re-selects language each session)
  - Blocks any other state from being set
```

---

## 4. Cache Registry

### 4.1 `@st.cache_data` Functions

| Function | TTL | Invalidated By | Used In |
|---|---|---|---|
| `get_cached_ledger()` | `ttl=30` (seconds) | `save_to_ledger()` calls `.clear()` | All pages that show financial data |
| `get_cached_tax_rules()` | No TTL (permanent) | Never at runtime | `pages/2_Scanner.py`, `pages/4_FPA.py` |

**Invalidation pattern for ledger:**
```python
# In engine/finance_engine.py → save_to_ledger():
def save_to_ledger(entry: dict) -> str:
    # ... write to CSV ...
    
    # Import here to avoid circular import at module level
    import streamlit as st
    # This requires get_cached_ledger to be defined at module level in the calling page
    # Solution: pages call st.cache_data.clear() after save, or use ledger_cache_key
    st.session_state["ledger_cache_key"] += 1  # Triggers re-fetch on next access
    return entry_id
```

**Alternative pattern (preferred — keeps engine free of Streamlit):**
```python
# In pages — after calling save_to_ledger():
save_to_ledger(entry)
st.cache_data.clear()   # Clears ALL cache — acceptable for single-user app
```

### 4.2 `@st.cache_resource` Functions

| Resource | Purpose | Notes |
|---|---|---|
| `get_claude_client()` | Single Anthropic client instance | Initialised once per session, shared across pages |

```python
@st.cache_resource
def get_claude_client() -> anthropic.Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in environment")
    return anthropic.Anthropic(api_key=api_key)
```

---

## 5. What Is Recomputed on Every Rerun

Streamlit reruns the entire page script on every widget interaction. These computations happen every rerun and must be fast:

| Computation | Rerun Cost | Mitigation |
|---|---|---|
| `get_cached_ledger()` | Near-zero (cached) | 30s TTL cache |
| `get_cached_tax_rules()` | Near-zero (cached) | Permanent cache |
| `get_current_quarter()` | Near-zero | Pure date math |
| `get_quarterly_summary(df, quarter)` | Fast (pandas groupby) | ~10ms for typical ledger size |
| `build_system_prompt(...)` | Fast (string formatting) | ~1ms |
| `render_lang_switcher()` | Near-zero | Two st.button calls |
| `render_sidebar()` | Fast | All cached data |

**What must NOT happen on every rerun:**
- API calls to Claude (only on explicit user action)
- OCR processing (only when "Analyze" button clicked)
- Gmail polling (only when timer condition met)
- `save_to_ledger()` (only when "Save" button clicked)

**Guard pattern for expensive operations:**
```python
# WRONG — runs on every rerun:
result = process_document(file_bytes, ...)

# CORRECT — runs only when button clicked:
if st.button(t("scanner.btn_analyze")):
    with st.spinner(t("scanner.spinner_analyzing")):
        result = process_document(file_bytes, ...)
        st.session_state["processed_document"] = result
```

---

## 6. Ghost Bug Prevention Checklist

Before adding any new state to the app, verify:

- [ ] Key registered in Section 2 of this document
- [ ] Default value set in `init_session_state()` in `app.py`
- [ ] Only one page is responsible for SETTING the value
- [ ] All pages that READ the value use `.get(key, default)` (never bare `[key]`)
- [ ] If the state should survive page navigation: `st.session_state`
- [ ] If the state is expensive to compute: `@st.cache_data`
- [ ] If the state must persist across sessions: write to `data/` via engine function
- [ ] If the state should NOT survive rerun: it should be a local variable, not session state

**Most common ghost bugs:**
1. Reading `st.session_state["key"]` before it's initialized → KeyError on fresh session
2. Using `st.session_state["key"] = value` inside a form → value set before submit, causes double-trigger
3. Calling `save_to_ledger()` without clearing cache → stale data shown after save
4. Building system prompt with stale `user_profile` → chatbot has wrong context
5. Checking `if uploaded_file:` outside a button guard → re-processes file on every widget interaction
