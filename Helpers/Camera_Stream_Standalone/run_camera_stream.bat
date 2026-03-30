@echo off
REM Portable launcher for Camera Stream (with Thorlabs support when run via Python).
REM
REM Usage on any Windows PC:
REM   1. Unzip this folder (including the .venv, if present).
REM   2. Double‑click this .bat file.
REM
REM If a local virtual environment exists in ".venv", use it.
REM Otherwise fall back to any "python" on PATH.

setlocal
set "SCRIPT_DIR=%~dp0"

REM Prefer local venv next to this folder if present (repo-level .venv)
if exist "%SCRIPT_DIR%..\..\Scripts\python.exe" (
    "%SCRIPT_DIR%..\..\Scripts\python.exe" "%SCRIPT_DIR%camera_stream_app.py"
    goto :end
)

REM Fallback: venv inside this folder (if you choose to create one here)
if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    "%SCRIPT_DIR%.venv\Scripts\python.exe" "%SCRIPT_DIR%camera_stream_app.py"
    goto :end
)

REM Last resort: system python on PATH
python "%SCRIPT_DIR%camera_stream_app.py"

:end
endlocal







