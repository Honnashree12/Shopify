# Local Developer Setup Guide (`docs/LOCAL_SETUP.md`)

This guide provides step-by-step instructions for setting up and running the **Shopify Product Launch & Validation Platform** on a local development environment.

---

## ⚙️ Prerequisites

Before you begin, ensure you have the following installed:

1. **Python**: Version `3.11` or higher.
   - Verify installation: `python --version` (or `python3 --version`)
2. **Node.js**: Version `18.0.0` or higher (with `npm`).
   - Verify installation: `node -v` and `npm -v`
3. **Git**: Version `2.30+`.
4. **Shopify Store Access**: A Shopify Development store or live admin store.
5. **Google AI Key**: Gemini API key from Google AI Studio.

---

## 🛠️ Step-by-Step Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/your-org/shopify-product-launch.git
cd shopify-product-launch
```

---

### Step 2: Set Up Python Backend Environment

1. Create a virtual environment:
   - **Windows**:
     ```bash
     python -m venv venv
     venv\Scripts\activate
     ```
   - **Linux / macOS**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```

2. Upgrade pip and install Python dependencies:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

### Step 3: Set Up Frontend Environment

1. Navigate to the `frontend` folder:
   ```bash
   cd frontend
   ```

2. Install Node.js dependencies:
   ```bash
   npm install
   ```

3. Return to the root directory:
   ```bash
   cd ..
   ```

---

### Step 4: Configure Environment Variables

> [!IMPORTANT]
> **No Credentials Policy**: Real credentials are never committed to Git. `.env` is listed in `.gitignore`.

1. Copy `.env.example` to create your local `.env` file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your specific credentials:

```ini
# Core Application Settings
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000

# Primary Shopify Store
SHOPIFY_STORE_URL=your-store.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_your_admin_access_token_here

# Shopify Partner App OAuth (If using OAuth flow)
SHOPIFY_CLIENT_ID=your_client_id_here
SHOPIFY_CLIENT_SECRET=your_client_secret_here

# Google Gemini / ADK API Key
GEMINI_API_KEY=your_gemini_api_key_here
```

---

## 🚀 Running the Platform

### Terminal 1: Backend Server (FastAPI)

From the project root directory (with virtual environment active):
```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```
- Server URL: `http://127.0.0.1:8000`
- Interactive API Documentation: `http://127.0.0.1:8000/docs`

---

### Terminal 2: Frontend Dashboard (Vite + React)

Open a new terminal, navigate to `frontend`:
```bash
cd frontend
npm run dev
```
- Local Console URL: `http://localhost:5173`
- Product Validation Dashboard: `http://localhost:5173/validation`

---

## 🧪 Running Tests

### Integration Test Suite
Run the primary workshop platform integration test suite:
```bash
python run_tests.py
```

### Unit Test Suite
Run unit tests across the test module:
```bash
python -m unittest discover tests
```

---

## ❓ Troubleshooting & FAQs

### Missing Configuration Error on Startup
If you see the error:
`CRITICAL STARTUP ERROR: MISSING SHOPIFY CONFIGURATION`
Ensure you have created a `.env` file in the root directory from `.env.example` and set `SHOPIFY_STORE_URL` and `SHOPIFY_ACCESS_TOKEN`.
