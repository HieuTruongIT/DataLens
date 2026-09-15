@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo DataTriage environment is missing.
    echo Run: python -m venv .venv
    echo Then: .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m streamlit run app.py --server.address=127.0.0.1 --server.port=8502 %*
if errorlevel 1 (
    echo DataTriage could not start. Check the message above.
    pause
    exit /b 1
)
endlocal
