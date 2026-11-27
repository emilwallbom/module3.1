@echo off
cd /d "%~dp0"
echo This explicitly selects terminal slack from the authors' code, not hard terminal equality from the paper.
echo This full-size variant is experimental and its learning benchmark has not passed.
".venv\Scripts\python.exe" scripts\launch.py play --terminal-mode author-soft
if errorlevel 1 pause
