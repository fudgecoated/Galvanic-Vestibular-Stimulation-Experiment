@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%..\.."
set "VENV_PYTHON=%REPO_ROOT%\.venv\Scripts\python.exe"
set "SCRIPT_PATH=%SCRIPT_DIR%scripts\trial_randomizer.py"

if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" -c "import reportlab" >nul 2>&1
    if not errorlevel 1 (
        "%VENV_PYTHON%" "%SCRIPT_PATH%"
        exit /b %errorlevel%
    )
)

python -c "import reportlab" >nul 2>&1
if errorlevel 1 (
    echo reportlab is not installed.
    echo Install it in the project environment with:
    echo   .\.venv\Scripts\pip install -r .\code\experiment\requirements.txt
    exit /b 1
)

python "%SCRIPT_PATH%"
exit /b %errorlevel%
