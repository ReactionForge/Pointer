@echo off
if exist "%~dp0Pointer.exe" (
  "%~dp0Pointer.exe" %*
  exit /b
)
where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%~dp0pointer_app.py" %*
  exit /b
)
python "%~dp0pointer_app.py" %*
if errorlevel 1 pause
