@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" scripts\package_portable.py
if errorlevel 1 pause
