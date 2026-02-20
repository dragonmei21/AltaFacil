# ENVIRONMENT.md — Alta Fácil Pro

> **What this document is:** Everything needed to go from zero to running app. Follow these steps exactly. If the app doesn't run after following this, something in this document needs updating.

---

## 1. System Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| Python | 3.11 | 3.12 |
| OS | macOS 12+ / Ubuntu 20.04+ | macOS 14 / Ubuntu 22.04 |
| RAM | 4 GB | 8 GB |
| Disk | 500 MB free | 2 GB free |
| Internet | Required for Claude API | Required for Claude API |

**Windows:** Not officially supported. WSL2 with Ubuntu 22.04 will work but is not tested.

---

## 2. System Dependencies (Install Before pip)

These are binary system packages — `pip` cannot install them.

### macOS (Homebrew)
```bash
# Install Homebrew if not present
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install tesseract
brew install tesseract-lang      # Includes Spanish (spa) language pack
brew install poppler             # Required by pdf2image

# Verify
tesseract --version              # Should show 5.x
tesseract --list-langs           # Should include 'spa'
pdftoppm -v                      # Should show poppler version
```

### Ubuntu / Debian / WSL2
```bash
sudo apt update
sudo apt install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    poppler-utils \
    libgl1-mesa-glx              # Required by opencv-python

# Verify
tesseract --version
tesseract --list-langs           # Should include 'spa'
pdftoppm -v
```

### Verification test
```bash
# Test OCR works on a simple image
python3 -c "import pytesseract; print(pytesseract.get_tesseract_version())"
# Expected: 5.x.x or 4.x.x
```

---

## 3. Python Environment Setup

```bash
# Clone / create project directory
cd ~/projects
mkdir altafacil_pro && cd altafacil_pro

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows (WSL: use the Linux command above)

# Verify Python version
python --version                 # Should show Python 3.11.x or 3.12.x

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### `requirements.txt` (copy verbatim)
```
# Frontend
streamlit>=1.35.0
plotly>=5.18.0
pandas>=2.0.0
python-dotenv>=1.0.0

# AI & Document Intelligence
anthropic>=0.25.0
pillow>=10.0.0
pytesseract>=0.3.10
opencv-python>=4.9.0.80
pdfplumber>=0.10.0
pdf2image>=1.16.3

# External Integrations
simplegmail>=4.2.0
google-auth-oauthlib>=1.2.0
google-api-python-client>=2.120.0
requests>=2.31.0

# Utilities
python-dateutil>=2.8.0
pytz>=2024.1
```

---

## 4. Environment Variables

### Required
| Variable | Description | How to Get |
|---|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key | console.anthropic.com → API Keys |

### Optional (for integrations)
| Variable | Default | Description |
|---|---|---|
| `GMAIL_DEMO_MODE` | `"true"` | `"true"` = use mock data, `"false"` = real Gmail OAuth |
| `GMAIL_CREDENTIALS_PATH` | `"credentials.json"` | Path to Google OAuth credentials file |
| `CALENDLY_DEMO_MODE` | `"true"` | `"true"` = use mock data, `"false"` = real Calendly API |
| `CALENDLY_ACCESS_TOKEN` | `""` | Calendly personal access token |

### Setup
```bash
# Copy the template
cp .env.example .env

# Edit .env with your actual values
nano .env   # or: code .env, vim .env, open .env
```

### `.env.example` (commit this file, never commit `.env`)
```
# Required
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE

# Optional — Gmail integration
GMAIL_DEMO_MODE=true
GMAIL_CREDENTIALS_PATH=credentials.json

# Optional — Calendly integration
CALENDLY_DEMO_MODE=true
CALENDLY_ACCESS_TOKEN=
```

### `.gitignore` entries (verify these exist)
```
.env
credentials.json
data/ledger.csv
data/user_profile.json
__pycache__/
.venv/
*.pyc
.DS_Store
```

---

## 5. Data Directory Initialization

```bash
# Create data directory if it doesn't exist
mkdir -p data

# The app creates these files automatically on first run:
#   data/ledger.csv       — created by finance_engine.load_ledger() if missing
#   data/user_profile.json — created by onboarding page on first run

# This file must be created manually before first run:
cp data/tax_rules_2025.json.example data/tax_rules_2025.json
# Or: the full JSON content is in CLAUDE.md Section 3.3
```

---

## 6. Gmail OAuth Setup (Optional — only if GMAIL_DEMO_MODE=false)

```bash
# Step 1: Go to Google Cloud Console
# https://console.cloud.google.com/

# Step 2: Create a new project (or use existing)

# Step 3: Enable Gmail API
# APIs & Services → Library → Gmail API → Enable

# Step 4: Create OAuth credentials
# APIs & Services → Credentials → Create Credentials → OAuth client ID
# Application type: Desktop app
# Download the JSON file → save as credentials.json in project root

# Step 5: Set environment variables
# In .env:
GMAIL_DEMO_MODE=false
GMAIL_CREDENTIALS_PATH=credentials.json

# Step 6: First run will open browser for OAuth consent
# After consent, a token.json file is created automatically by simplegmail
```

---

## 7. Calendly API Setup (Optional — only if CALENDLY_DEMO_MODE=false)

```bash
# Step 1: Go to Calendly Developer Portal
# https://developer.calendly.com/

# Step 2: Get a Personal Access Token
# Integrations → API & Webhooks → Personal Access Tokens → Generate New Token

# Step 3: Set environment variable
# In .env:
CALENDLY_DEMO_MODE=false
CALENDLY_ACCESS_TOKEN=your_token_here

# OR: Enter the token in the app's sidebar UI — it will be stored in session state
```

---

## 8. Running the App

```bash
# Activate virtual environment (if not already active)
source .venv/bin/activate

# Run the app
streamlit run app.py

# Expected output:
#   You can now view your Streamlit app in your browser.
#   Local URL: http://localhost:8501
#   Network URL: http://192.168.x.x:8501

# Open browser to http://localhost:8501
# First run: you will be redirected to onboarding (pages/0_Onboarding.py)
```

### Useful run flags
```bash
# Run on different port
streamlit run app.py --server.port 8502

# Disable browser auto-open
streamlit run app.py --server.headless true

# Enable file watcher for development (default: already on)
streamlit run app.py --server.runOnSave true
```

---

## 9. Verifying the Installation

Run this script to verify all dependencies work:

```bash
python3 - << 'EOF'
print("Checking dependencies...")

try:
    import streamlit; print(f"✅ streamlit {streamlit.__version__}")
except ImportError as e: print(f"❌ streamlit: {e}")

try:
    import anthropic; print(f"✅ anthropic {anthropic.__version__}")
except ImportError as e: print(f"❌ anthropic: {e}")

try:
    import cv2; print(f"✅ opencv {cv2.__version__}")
except ImportError as e: print(f"❌ opencv: {e}")

try:
    import pytesseract
    v = pytesseract.get_tesseract_version()
    print(f"✅ pytesseract (tesseract {v})")
except Exception as e: print(f"❌ pytesseract/tesseract: {e}")

try:
    import pdfplumber; print(f"✅ pdfplumber {pdfplumber.__version__}")
except ImportError as e: print(f"❌ pdfplumber: {e}")

try:
    import pdf2image; print(f"✅ pdf2image")
except ImportError as e: print(f"❌ pdf2image: {e}")

try:
    import plotly; print(f"✅ plotly {plotly.__version__}")
except ImportError as e: print(f"❌ plotly: {e}")

try:
    import pandas; print(f"✅ pandas {pandas.__version__}")
except ImportError as e: print(f"❌ pandas: {e}")

import os
from dotenv import load_dotenv
load_dotenv()
key = os.getenv("ANTHROPIC_API_KEY", "")
if key.startswith("sk-ant-"):
    print(f"✅ ANTHROPIC_API_KEY set")
else:
    print(f"❌ ANTHROPIC_API_KEY missing or invalid (check .env)")

print("\nAll checks complete.")
EOF
```

---

## 10. Common Setup Errors

| Error | Cause | Fix |
|---|---|---|
| `TesseractNotFoundError` | tesseract binary not in PATH | Run `brew install tesseract` or `sudo apt install tesseract-ocr` |
| `Error: Language spa not available` | Spanish pack missing | `brew install tesseract-lang` or `sudo apt install tesseract-ocr-spa` |
| `pdftoppm: command not found` | poppler not installed | `brew install poppler` or `sudo apt install poppler-utils` |
| `ImportError: libGL.so.1` | OpenCV system lib missing (Linux) | `sudo apt install libgl1-mesa-glx` |
| `anthropic.AuthenticationError` | API key wrong or missing | Check `.env` file, verify key at console.anthropic.com |
| `ModuleNotFoundError: simplegmail` | Not installed | `pip install simplegmail` |
| `streamlit: command not found` | venv not activated | `source .venv/bin/activate` |
| `FileNotFoundError: data/tax_rules_2025.json` | Data file missing | Copy from CLAUDE.md Section 3.3 |

---

## 11. Deployment (for Assignment Demo)

### Option A — Loom Video (Recommended for Assignment)
```bash
# Run locally, record with Loom
# https://www.loom.com/
# No deployment needed
```

### Option B — Streamlit Cloud
```bash
# 1. Push to GitHub (public or private repo)
# 2. Go to https://share.streamlit.io/
# 3. Connect GitHub account
# 4. Select repo and main file: app.py
# 5. Add secrets in Settings → Secrets:
#    ANTHROPIC_API_KEY = "sk-ant-..."
#    GMAIL_DEMO_MODE = "true"
#    CALENDLY_DEMO_MODE = "true"
# 6. Deploy — get public URL in ~2 minutes
```

### Option C — Hugging Face Spaces
```bash
# 1. Go to https://huggingface.co/spaces
# 2. Create new Space → SDK: Streamlit
# 3. Push code to the Space repo
# 4. Add secrets in Settings → Repository secrets
# 5. Space auto-deploys on push
```

### Note on requirements for cloud deployment
Add to `packages.txt` in project root (Streamlit Cloud / HF Spaces reads this for apt packages):
```
tesseract-ocr
tesseract-ocr-spa
poppler-utils
libgl1-mesa-glx
```
