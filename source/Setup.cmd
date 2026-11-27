@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -File scripts\setup.ps1
pause
