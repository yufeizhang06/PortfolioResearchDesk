@echo off
cd /d "%~dp0"
if exist "work\bin\uv.exe" (
  "work\bin\uv.exe" sync --locked --extra gui --extra factors --extra data --extra ml --python 3.12
) else (
  where uv >nul 2>&1
  if errorlevel 1 (
    py -3.12 -m uv sync --locked --extra gui --extra factors --extra data --extra ml --python 3.12
  ) else (
    uv sync --locked --extra gui --extra factors --extra data --extra ml --python 3.12
  )
)
if errorlevel 1 (
  echo Setup failed. Python 3.12 and uv 0.13.6 are required. See README.md.
  pause
  exit /b 2
)
echo Setup complete. Double-click Start GUI.cmd.
pause
exit /b 0
