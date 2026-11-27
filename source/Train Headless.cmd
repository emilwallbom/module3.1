@echo off
cd /d "%~dp0"
set OPENBLAS_NUM_THREADS=1
set OMP_NUM_THREADS=1
".venv\Scripts\python.exe" -m racing.train %*
pause
