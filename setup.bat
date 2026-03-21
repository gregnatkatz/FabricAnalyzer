@echo off
REM ============================================================
REM Fabric Data Agent Analyzer — One-Click Setup (Windows)
REM ============================================================
REM Double-click this file or run from Command Prompt.
REM No coding knowledge required.
REM ============================================================

echo.
echo   ==============================================
echo    Fabric Data Agent Analyzer -- Setup
echo    Latency diagnostics for Microsoft Fabric
echo   ==============================================
echo.

REM -- Check Node.js --
echo [1/8] Checking Node.js...
where node >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo   ERROR: Node.js not found.
    echo   Install from https://nodejs.org/ (LTS recommended)
    echo   After installing, close and reopen your terminal, then run this script again.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('node -v') do echo   OK Node.js %%i found

REM -- Check Python --
echo [2/8] Checking Python 3...
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    where python3 >nul 2>nul
    if %ERRORLEVEL% neq 0 (
        echo   ERROR: Python 3 not found.
        echo   Install from https://python.org/ (3.10+ recommended)
        echo   After installing, close and reopen your terminal, then run this script again.
        pause
        exit /b 1
    )
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo   OK %%i found

REM -- Install Node dependencies --
echo [3/8] Installing Node.js dependencies...
call npm install --silent 2>nul
echo   OK Root dependencies installed
cd client && call npm install --silent 2>nul && cd ..
echo   OK Client dependencies installed
cd server && call npm install --silent 2>nul && cd ..
echo   OK Server dependencies installed

REM -- Install Python dependencies --
echo [4/8] Installing Python dependencies...
python -m pip install --quiet chromadb numpy requests 2>nul
echo   OK Python packages installed

REM -- Configure environment --
echo [5/8] Configuring environment...
if not exist server\.env (
    (
        echo # Fabric Data Agent Analyzer -- Environment Configuration
        echo # Replace LLM_ENDPOINT and LLM_API_KEY with your Azure AI values.
        echo # Sample Dataset mode works without them.
        echo.
        echo LLM_ENDPOINT=https://your-resource.openai.azure.com/openai/v1
        echo LLM_API_KEY=placeholder-api-key
        echo LLM_MODEL=DeepSeek-V3.2-Speciale
        echo CHROMADB_PATH=../chroma_db
        echo SQLITE_DIR=./data
        echo TMP_DIR=./tmp
        echo SYNTHETIC_ROW_SCALE=0.025
        echo BATTERY_TIMEOUT_MS=30000
        echo CALIBRATION_FACTOR=3.2
        echo MONTE_CARLO_N=500
        echo PORT=3001
        echo PYTHON_PATH=python
    ) > server\.env
    echo   OK Created server\.env
    echo   NOTE: Edit server\.env with your Azure AI endpoint and API key to enable AI agents
    echo   Sample Dataset mode works without an API key -- great for a quick demo
) else (
    echo   OK server\.env already exists
)

if not exist server\data mkdir server\data
if not exist server\tmp mkdir server\tmp
echo   OK Data directories ready

REM -- Build sample dataset --
echo [6/8] Building sample dataset...
if exist sample_dataset\sample.db (
    echo   OK sample.db already exists
) else (
    if exist sample_dataset\build_sample.py (
        python sample_dataset\build_sample.py 2>nul
        echo   OK Sample dataset built
    ) else (
        echo   WARNING: build_sample.py not found -- sample dataset will be built on first use
    )
)

REM -- Build ChromaDB knowledge base --
echo [7/8] Building ChromaDB knowledge base (500 issue patterns)...
if exist chroma_db\chroma.sqlite3 (
    echo   OK ChromaDB already populated
) else (
    if exist knowledge\embedder.py (
        python knowledge\embedder.py 2>nul
        echo   OK Knowledge base built
    ) else (
        echo   WARNING: embedder.py not found -- knowledge base not built
    )
)

REM -- Start the app --
echo [8/8] Starting the app...
echo.
echo   Setup complete!
echo.
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:3001
echo.
echo   Quick Start:
echo   1. Open http://localhost:5173 in your browser
echo   2. Click "Sample Dataset" to load demo data (no Azure AI key required)
echo   3. Click "Run Analysis" on the Workflow tab
echo   4. Explore Findings, Simulation, and Validation tabs
echo   5. Export PDF from the Artifacts tab
echo.
echo   To connect to a real Fabric Data Agent:
echo   1. Edit server\.env with your Azure AI endpoint and API key
echo   2. Paste a Fabric token on the Connect tab
echo   3. See README.md for full instructions
echo.
echo   9-Agent AI Pipeline:
echo   Domain Intelligence - Adversarial Probe - Schema - DAX - Execution
echo   - Synthesis - Monte Carlo (500 sims) - Remediation - Validation
echo.
echo   Supported Models: GPT-5.4 Pro, DeepSeek V3.2 Speciale, DeepSeek V3.2, GPT-4o
echo   Each agent can use a different model -- configure on the Workflow tab
echo.
echo   Press Ctrl+C to stop the servers
echo.

call npm run dev
