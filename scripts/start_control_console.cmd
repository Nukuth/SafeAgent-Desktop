@echo off
setlocal
set "ROOT=%~dp0.."
cd /d "%ROOT%"

if not exist ".venv\Scripts\uvicorn.exe" (
  echo Missing .venv\Scripts\uvicorn.exe
  echo Run dependency setup before starting the control console.
  exit /b 1
)

if not defined SAFEAGENT_ENV_FILE (
  set "SAFEAGENT_ENV_FILE=%ROOT%\.env.local"
)

echo Starting SafeAgent Control Console
echo URL: http://127.0.0.1:8080
echo Env file: %SAFEAGENT_ENV_FILE%
".venv\Scripts\uvicorn.exe" safeagent.server.app:create_app --factory --host 127.0.0.1 --port 8080
