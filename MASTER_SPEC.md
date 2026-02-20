# MASTER_SPEC.md — Alta Fácil Pro

> **What this document is:** The product specification. What the system must do, for whom, and why.
> No code. No implementation details. Those live in CLAUDE.md and ARCHITECTURE.md.

---

## 1. Problem Statement

Spanish autónomos (self-employed / freelancers) face a uniquely painful financial admin burden:

- They must file **4 quarterly VAT returns** (Modelo 303) and **4 quarterly income tax prepayments** (Modelo 130) per year
- Every business expense must be manually classified by IVA rate (21% / 10% / 4% / exempt) and deductibility percentage (100% / 50% / 30% / 0%) under Spanish law
- Most autónomos discover they owe thousands in taxes only when their gestor (accountant) calls — with days to spare before the deadline
- Existing tools (Holded, Contasimple, Qdadmin) are either too expensive, too complex, or require ongoing gestor involvement
- ~3.3 million autónomos in Spain. ~40% are first-time freelancers who don't understand the tax system

**The core pain:** Surprise tax bills. Every. Quarter.

**The solution:** A real-time AI financial dashboard that processes invoices as they happen, classifies them automatically under Spanish tax law, and shows exactly what the user will owe — before the deadline arrives.

---

## 2. User Personas

### Persona A — "María, la Consultora" (Primary)
- **Age:** 32
- **Activity:** Digital marketing consultant, 2 years as autónoma
- **Revenue:** €2,500–4,000/month, mostly from 3-4 long-term clients
- **Pain:** Loses track of expenses, always surprised by the quarterly Modelo 303
- **Tech comfort:** High — uses Notion, Slack, Google Workspace
- **Language:** Spanish, some English
- **Goal:** Know what she owes in real time. Stop being surprised.

### Persona B — "James, the Expat Freelancer" (Secondary)
- **Age:** 29
- **Activity:** UX designer, recently registered as autónomo after relocating from the UK
- **Revenue:** €1,800–2,500/month, 1-2 clients, invoices in EUR and sometimes GBP
- **Pain:** Doesn't understand the Spanish tax system. Confused by "Modelo 303", "IVA repercutido", "base imponible"
- **Tech comfort:** Very high — developer background
- **Language:** English primary, learning Spanish
- **Goal:** Understand what these Spanish tax terms mean and not make costly mistakes in his first year

### Persona C — "Carlos, el Profesional Liberal" (Secondary)
- **Age:** 45
- **Activity:** Physiotherapist with private practice
- **Revenue:** €3,000–5,000/month, 20–30 patients/week, paid by session
- **Pain:** Many small transactions, receipts piling up, exempt from IVA (Art. 20) but still needs to track expenses
- **Tech comfort:** Medium — uses WhatsApp and iPhone, not a power user
- **Language:** Spanish only
- **Goal:** Quick receipt capture, especially on mobile. Know his deductible expenses.

---

## 3. Feature List

### MVP Features (must be in v1)

| # | Feature | Persona | Value |
|---|---|---|---|
| F1 | **Invoice / receipt scanner** — upload PDF, photo, or manual entry | A, B, C | Eliminates manual data entry |
| F2 | **AI field extraction** — OCR + Claude extracts all invoice fields | A, B, C | Turns a photo into structured data |
| F3 | **Automatic IVA classification** — deterministic rules engine (21%/10%/4%/exempt) | A, B, C | No more guessing the rate |
| F4 | **Deductibility classification** — 100%/50%/30%/0% with legal citation | A, B | Maximises deductions legally |
| F5 | **Live ledger** — all AP/AR entries in one scrollable, filterable table | A, B, C | Single source of truth |
| F6 | **Quarterly FP&A** — real-time Modelo 303 and Modelo 130 projections | A, B | No more tax surprises |
| F7 | **What-if simulator** — sliders to project future revenue/expenses | A, B | Planning ahead |
| F8 | **AI chatbot (El Gestor)** — answers tax questions using live ledger data | A, B | Personalised answers, not generic advice |
| F9 | **Bilingual UI** — full ES/EN toggle, Spanish tax terms with English tooltips | B | Removes language barrier for expats |
| F10 | **Onboarding quiz** — personalises tax rules (home office %, tarifa plana, etc.) | A, B, C | Context-aware classifications |
| F11 | **Deadline countdown** — days until next Modelo 303/130 filing | A, C | Reduces deadline anxiety |

### Phase 2 Features (post-MVP, do not build in v1)

| # | Feature | Notes |
|---|---|---|
| F12 | Gmail auto-scan | Polls inbox for invoice attachments, auto-saves |
| F13 | Calendly integration | Converts bookings → AR draft invoices |
| F14 | Annual IRPF estimate | Full year income tax bracket projection |
| F15 | Export to PDF | Pre-filled Modelo 303/130 summary for gestor |
| F16 | Multi-currency | GBP/USD invoices converted at ECB rate |
| F17 | Verifactu compliance | Electronic invoicing (mandatory from 2027) |

### Never Build
- Multi-user / team accounts (single autónomo tool)
- Direct filing with AEAT (liability risk)
- Payroll (autónomos don't have payroll)

---

## 4. Constraints

### Legal / Compliance Constraints
- **Never file on behalf of user.** Display projections only. Always show disclaimer.
- **Tax classifications must cite the legal article** (e.g. "Art. 90.Uno Ley 37/1992"). User must be able to verify.
- **IVA rates must come from deterministic rules, never LLM output.** LLM hallucination on tax rates = legal liability.
- **Data stays local.** No sending user financial data to third parties beyond Anthropic (for chatbot) and Gmail/Calendly (opt-in only).

### Technical Constraints
- Python 3.11+
- Runs on macOS and Linux (no Windows-specific code)
- Single-user app — no authentication, no multi-tenancy
- Persistence: CSV + JSON only. No database setup required.
- Must work without internet for core features (except Claude API calls)
- `tesseract-ocr` must be installed as a system dependency (documented in ENVIRONMENT.md)

### UX Constraints
- Mobile-usable for receipt capture (camera widget must work on phone browser)
- Page load < 3 seconds (use `@st.cache_data` aggressively)
- All errors must surface to the user with actionable messages — no silent failures
- Every tax verdict must show the AEAT legal article so users can verify

### Scope Constraints (for this prototype)
- Gmail and Calendly integrations use demo mode by default (`GMAIL_DEMO_MODE=true`)
- No OAuth flow required for demo video
- Ledger is a flat CSV — no relational integrity needed

---

## 5. Non-Functional Requirements

| Requirement | Target | How Measured |
|---|---|---|
| **Invoice processing time** | < 10 seconds end-to-end (OCR + Claude + rules) | Manual timing during demo |
| **IVA classification accuracy** | 100% on common categories (software, hosting, transport, food) | Unit tests in `tests/test_tax_rules.py` |
| **Chatbot response time** | < 5 seconds | claude-sonnet-4-6 latency |
| **UI responsiveness** | No widget takes > 30s to update | Streamlit rerun profiling |
| **Ledger correctness** | IVA calculations accurate to €0.01 | Unit tests in `tests/test_finance_engine.py` |
| **Bilingual completeness** | 100% of UI strings translated (0 hardcoded strings) | `grep` check in CI |
| **Crash rate** | 0 unhandled exceptions reaching user | All engine calls wrapped in try/except |

---

## 6. Success Criteria (for PDAI Assignment)

The prototype is successful if a user can:
1. Complete onboarding in < 2 minutes
2. Upload a real Spanish invoice PDF and get a correct IVA + deductibility classification in < 10 seconds
3. See their quarterly Modelo 303 projection update in real time after saving an invoice
4. Ask the chatbot "how much VAT do I owe?" and get an answer citing their actual numbers
5. Switch between Spanish and English and have every string update instantly

---

## 7. Out of Scope

- Backend server / API (Streamlit handles this)
- User accounts / login / passwords
- Database (CSV + JSON is sufficient for prototype)
- Real AEAT filing integration
- Accountant-to-client portal
- Invoice generation / outgoing invoices (AR input only via Calendly or manual)
- Bank account sync (Plaid, Tink, etc.)
