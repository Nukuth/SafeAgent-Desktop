@echo off
setlocal
set "ROOT=%~dp0.."
set "ENV_FILE=%ROOT%\.env.local"

if not exist "%ENV_FILE%" (
  echo Missing %ENV_FILE%
  echo Create it from .env.example, then set SAFEAGENT_SERVER_TOKEN.
  exit /b 1
)

for /f "usebackq tokens=1,* delims==" %%A in ("%ENV_FILE%") do (
  if /i "%%A"=="SAFEAGENT_SERVER_TOKEN" (
    echo SAFEAGENT_SERVER_TOKEN=%%B
    exit /b 0
  )
)

echo SAFEAGENT_SERVER_TOKEN was not found in %ENV_FILE%
exit /b 1
