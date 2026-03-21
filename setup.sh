#!/usr/bin/env bash
# ============================================================
# Fabric Data Agent Analyzer — One-Click Setup
# ============================================================
# Run this script to install all prerequisites and start the app.
# Works on macOS and Linux. No coding knowledge required.
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh
#
# Or run directly:
#   bash setup.sh
# ============================================================

set -o pipefail

# Colors for output (disabled if not a terminal)
if [ -t 1 ]; then
  RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
  BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'
else
  RED=''; GREEN=''; YELLOW=''; BLUE=''; CYAN=''; NC=''; BOLD=''
fi

print_step() { echo -e "\n${CYAN}${BOLD}[$1/$TOTAL_STEPS]${NC} ${BOLD}$2${NC}"; }
print_ok()   { echo -e "  ${GREEN}OK${NC} $1"; }
print_warn() { echo -e "  ${YELLOW}WARNING${NC} $1"; }
print_err()  { echo -e "  ${RED}ERROR${NC} $1"; }

TOTAL_STEPS=9
ERRORS=0

# ── Navigate to repo root (where this script lives) ──────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${CYAN}${BOLD}"
echo "  =============================================="
echo "   Fabric Data Agent Analyzer -- Setup"
echo "   Latency diagnostics for Microsoft Fabric"
echo "  =============================================="
echo -e "${NC}"
echo -e "  Running from: ${BLUE}$SCRIPT_DIR${NC}"

# ── Step 1: Check Node.js ──────────────────────────────────
print_step 1 "Checking Node.js..."

if ! command -v node &>/dev/null; then
    print_err "Node.js not found"
    echo -e "  Install from: ${BLUE}https://nodejs.org/${NC} (LTS recommended)"
    echo "  Or run: brew install node (macOS) / sudo apt install nodejs npm (Ubuntu)"
    echo ""
    echo "  After installing, close and reopen your terminal, then run this script again."
    exit 1
fi

NODE_VER=$(node -v | sed 's/v//')
NODE_MAJOR=$(echo "$NODE_VER" | cut -d. -f1)
if [ "$NODE_MAJOR" -lt 18 ]; then
    print_err "Node.js v$NODE_VER found, but v18+ is required"
    echo -e "  Install from: ${BLUE}https://nodejs.org/${NC}"
    exit 1
fi
print_ok "Node.js v$NODE_VER"

if ! command -v npm &>/dev/null; then
    print_err "npm not found (should come with Node.js)"
    echo -e "  Install from: ${BLUE}https://nodejs.org/${NC}"
    exit 1
fi
print_ok "npm v$(npm -v)"

# ── Step 2: Check Python ──────────────────────────────────
print_step 2 "Checking Python 3..."

PYTHON_CMD=""
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PY_MAJOR=$(python --version 2>&1 | grep -o '^Python [0-9]\+' | grep -o '[0-9]\+' || echo "0")
    if [ "${PY_MAJOR}" -eq 3 ] 2>/dev/null; then
        PYTHON_CMD="python"
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    print_err "Python 3 not found"
    echo -e "  Install from: ${BLUE}https://python.org/${NC} (3.10+ recommended)"
    echo "  Or run: brew install python3 (macOS) / sudo apt install python3 python3-pip (Ubuntu)"
    echo ""
    echo "  After installing, close and reopen your terminal, then run this script again."
    exit 1
fi
print_ok "$($PYTHON_CMD --version 2>&1)"

# Check pip
HAS_PIP=true
if ! $PYTHON_CMD -m pip --version &>/dev/null; then
    print_warn "pip not found — Python packages will be skipped"
    echo -e "  Install pip: ${BLUE}$PYTHON_CMD -m ensurepip --upgrade${NC}"
    HAS_PIP=false
fi

# ── Step 3: Install Node.js dependencies ──────────────────
print_step 3 "Installing Node.js dependencies..."

# Root dependencies (includes concurrently for npm run dev)
if npm install 2>&1 | tail -3; then
    print_ok "Root dependencies installed"
else
    print_err "Root npm install failed — check errors above"
    ERRORS=$((ERRORS + 1))
fi

# Client (React + Vite) — run in subshell so cd doesn't affect parent
if (cd client && npm install 2>&1 | tail -3); then
    print_ok "Client (React) dependencies installed"
else
    print_err "Client npm install failed"
    ERRORS=$((ERRORS + 1))
fi

# Server (Express) — run in subshell
if (cd server && npm install 2>&1 | tail -3); then
    print_ok "Server (Express) dependencies installed"
else
    print_err "Server npm install failed"
    ERRORS=$((ERRORS + 1))
fi

if [ "$ERRORS" -gt 0 ]; then
    print_err "$ERRORS npm install(s) failed — the app may not work correctly"
    echo "  Try running 'npm install' manually in each directory"
fi

# ── Step 4: Install Python dependencies ───────────────────
print_step 4 "Installing Python dependencies..."

if [ "$HAS_PIP" = true ]; then
    $PYTHON_CMD -m pip install --quiet chromadb 2>/dev/null \
        && print_ok "ChromaDB installed" \
        || print_warn "ChromaDB install failed (optional — needed for RAG grounding)"
    $PYTHON_CMD -m pip install --quiet numpy 2>/dev/null \
        && print_ok "NumPy installed" \
        || print_warn "NumPy install failed (optional)"
    $PYTHON_CMD -m pip install --quiet requests 2>/dev/null \
        && print_ok "Requests installed" \
        || print_warn "Requests install failed (needed for Fabric API calls)"
else
    print_warn "Skipping Python packages (pip not available)"
fi

# ── Step 5: Configure environment ─────────────────────────
print_step 5 "Configuring environment..."

if [ ! -f server/.env ]; then
    cat > server/.env << 'ENVFILE'
# ============================================================
# Fabric Data Agent Analyzer — Environment Configuration
# ============================================================
# Replace LLM_ENDPOINT and LLM_API_KEY with your Azure AI values
# to enable AI-powered analysis. Sample Dataset mode works without them.
#
# To get these values:
#   1. Go to https://ai.azure.com → your project → Deployments
#   2. Click on a deployed model → copy the Endpoint URL and Key
# ============================================================

# Azure AI endpoint and credentials
LLM_ENDPOINT=https://your-resource.openai.azure.com/openai/v1
LLM_API_KEY=placeholder-api-key
LLM_MODEL=DeepSeek-V3.2-Speciale

# Per-model endpoints (optional — falls back to LLM_ENDPOINT)
# Uncomment and set these if different models are on different endpoints
# LLM_ENDPOINT_GPT54=https://your-resource.openai.azure.com/openai/v1
# LLM_API_KEY_GPT54=your-gpt54-key
# LLM_ENDPOINT_DEEPSEEK=https://your-resource.openai.azure.com/openai/v1
# LLM_API_KEY_DEEPSEEK=your-deepseek-key

# Storage paths (defaults work fine — no need to change)
CHROMADB_PATH=../chroma_db
SQLITE_DIR=./data
TMP_DIR=./tmp

# Pipeline settings
SYNTHETIC_ROW_SCALE=0.025
BATTERY_TIMEOUT_MS=30000
CALIBRATION_FACTOR=3.2
MONTE_CARLO_N=500

# Server
PORT=3001
PYTHON_PATH=python3
ENVFILE
    print_ok "Created server/.env"
    print_warn "Edit server/.env with your Azure AI endpoint and API key to enable AI agents"
    echo -e "  ${YELLOW}Sample Dataset mode works without an API key — great for a quick demo${NC}"
else
    print_ok "server/.env already exists"
fi

# Ensure data directories exist
mkdir -p server/data server/tmp
print_ok "Data directories ready"

# ── Step 6: Build sample dataset ──────────────────────────
print_step 6 "Building sample dataset..."

if [ -f sample_dataset/sample.db ]; then
    print_ok "sample.db already exists"
else
    if [ -f sample_dataset/build_sample.py ]; then
        if $PYTHON_CMD sample_dataset/build_sample.py 2>&1; then
            print_ok "Sample dataset built"
        else
            print_warn "Sample dataset build failed (you can still use the app)"
        fi
    else
        print_warn "build_sample.py not found — sample dataset will be built on first use"
    fi
fi

# ── Step 7: Verify Puppeteer / PDF export ──────────────────
print_step 7 "Checking PDF export dependencies..."

# Puppeteer needs Chromium — check if it can launch
if command -v npx &>/dev/null; then
    # Just verify the puppeteer package is available (installed in step 3)
    if [ -d "server/node_modules/puppeteer" ] || [ -d "node_modules/puppeteer" ]; then
        print_ok "Puppeteer installed (PDF export available)"
    else
        print_warn "Puppeteer not found — PDF export may not work"
        echo -e "  Run: ${BLUE}cd server && npm install puppeteer${NC}"
    fi
else
    print_warn "npx not found — PDF export may not work"
fi

# ── Step 8: Build ChromaDB knowledge base ─────────────────
print_step 8 "Building ChromaDB knowledge base (500 issue patterns)..."

if [ -d chroma_db ] && [ "$(ls -A chroma_db 2>/dev/null)" ]; then
    print_ok "ChromaDB already populated"
else
    if [ -f knowledge/embedder.py ]; then
        if $PYTHON_CMD knowledge/embedder.py 2>&1; then
            print_ok "Knowledge base built (500+ issue patterns)"
        else
            print_warn "ChromaDB build failed (optional — app works without it)"
        fi
    else
        print_warn "embedder.py not found — knowledge base not built"
    fi
fi

# ── Step 9: Start the app ────────────────────────────────
print_step 9 "Starting the app..."

echo ""
echo -e "${GREEN}${BOLD}  Setup complete!${NC}"
echo ""
echo -e "  ${BOLD}Starting servers...${NC}"
echo -e "  Frontend: ${CYAN}http://localhost:5173${NC}"
echo -e "  Backend:  ${CYAN}http://localhost:3001${NC}"
echo ""
echo -e "  ${BOLD}Quick Start:${NC}"
echo -e "  1. Open ${CYAN}http://localhost:5173${NC} in your browser"
echo -e "  2. Click ${GREEN}\"Sample Dataset\"${NC} to load demo data (no Azure AI key required)"
echo -e "  3. Click ${GREEN}\"Run Analysis\"${NC} on the Workflow tab"
echo -e "  4. Explore Findings, Simulation, and Validation tabs"
echo -e "  5. Export PDF from the Artifacts tab"
echo ""
echo -e "  ${BOLD}To connect to a real Fabric Data Agent:${NC}"
echo -e "  1. Edit ${CYAN}server/.env${NC} with your Azure AI endpoint and API key"
echo -e "  2. Paste a Fabric token on the Connect tab"
echo -e "  3. See README.md for full instructions"
echo ""
echo -e "  ${BOLD}9-Agent AI Pipeline:${NC}"
echo -e "  Domain Intelligence → Adversarial Probe → Schema → DAX → Execution"
echo -e "  → Synthesis → Monte Carlo (500 sims) → Remediation → Validation"
echo ""
echo -e "  ${BOLD}Supported Models:${NC} GPT-5.4 Pro, DeepSeek V3.2 Speciale, DeepSeek V3.2, GPT-4o"
echo -e "  Each agent can use a different model — configure on the Workflow tab"
echo ""
echo -e "  Press ${YELLOW}Ctrl+C${NC} to stop the servers"
echo ""

npm run dev
