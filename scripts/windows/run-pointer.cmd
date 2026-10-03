@echo off
set "pointerEntry=%~dp0..\..\packaging\windows\entrypoint.py"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%pointerEntry%" %*
  exit /b
)
python "%pointerEntry%" %*
if errorlevel 1 pause
