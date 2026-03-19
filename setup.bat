@echo off
REM ============================================================
REM Fabric Data Agent Analyzer — One-Click Setup (Windows)
REM ============================================================
REM Double-click this file or run from Command Prompt.
REM ============================================================

echo.
echo   ============================================
echo    Fabric Data Agent Analyzer — Setup
echo    Latency diagnostics for Microsoft Fabric
echo   ============================================
echo.

REM -- Check Node.js --
echo [1/6] Checking Node.js...
where node >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo   ERROR: Node.js not found. Install from https://nodejs.org/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('node -v') do echo   OK Node.js %%i found

REM -- Check Python --
echo [2/6] Checking Python 3...
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    where python3 >nul 2>nul
    if %ERRORLEVEL% neq 0 (
        echo   ERROR: Python 3 not found. Install from https://python.org/
        pause
        exit /b 1
    )
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo   OK %%i found

REM -- Install Node dependencies --
echo [3/6] Installing Node.js dependencies...
call npm install --silent 2>nul
echo   OK Root dependencies installed
cd client && call npm install --silent 2>nul && cd ..
echo   OK Client dependencies installed
cd server && call npm install --silent 2>nul && cd ..
echo   OK Server dependencies installed

REM -- Install Python dependencies --
echo [4/6] Installing Python dependencies...
python -m pip install --quiet chromadb numpy 2>nul
echo   OK Python packages installed

REM -- Configure environment --
echo [5/6] Configuring environment...
if not exist server\.env (
    (
        echo LLM_ENDPOINT=https://your-resource.openai.azure.com/openai/v1
        echo LLM_API_KEY=placeholder-api-key
        echo LLM_MODEL=gpt-4o
        echo CHROMADB_PATH=../chroma_db
        echo SQLITE_DIR=./data
        echo TMP_DIR=./tmp
        echo MONTE_CARLO_N=500
        echo PORT=3001
        echo PYTHON_PATH=python
    ) > server\.env
    echo   OK Created server\.env (edit with your Azure OpenAI credentials)
    echo   WARNING: LLM agents won't work until you add a real API key
) else (
    echo   OK server\.env already exists
)

REM -- Start the app --
echo [6/6] Starting the app...
echo.
echo   Setup complete!
echo.
echo   Frontend: http://localhost:5173
echo   Backend:  http://localhost:3001
echo.
echo   Quick Start:
echo   1. Open http://localhost:5173 in your browser
echo   2. Click "Sample Dataset" to load demo data
echo   3. Explore Traces, Findings, Simulation tabs
echo   4. Export PDF from Artifacts tab
echo.
echo   Press Ctrl+C to stop the servers
echo.

call npm run dev
