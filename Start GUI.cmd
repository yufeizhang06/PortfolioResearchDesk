@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please run Setup GUI.cmd first.
  pause
  exit /b 2
)
".venv\Scripts\python.exe" -m portfolio_research_desk.gui.launch
set "PRD_GUI_EXIT=%ERRORLEVEL%"
if not "%PRD_GUI_EXIT%"=="0" pause
exit /b %PRD_GUI_EXIT%
