@echo off
cd /d "%~dp0"
echo Paper equations comparison: 1.2 s, data-only regression, hard terminal equality.
echo The user-defined half-width overhang rule still applies. This full-size comparison may become infeasible.
".venv\Scripts\python.exe" scripts\launch.py play --terminal-mode paper-hard
if errorlevel 1 pause
