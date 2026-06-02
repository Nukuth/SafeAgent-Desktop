@echo off
setlocal

set "ROOT=%~dp0.."
set "LLAMA_DIR=%ROOT%\tools\llama.cpp\b9444"
set "MODEL=%ROOT%\models\Qwen_Qwen3.5-35B-A3B-Q4_K_M.gguf"
set "LOGDIR=%ROOT%\.runtime\llama-server"

if not exist "%LLAMA_DIR%\llama-server.exe" (
  echo FAIL: llama-server.exe not found at "%LLAMA_DIR%\llama-server.exe"
  exit /b 1
)

if not exist "%MODEL%" (
  echo FAIL: Qwen model not found at "%MODEL%"
  exit /b 1
)

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

start "SafeAgent llama-server" /min powershell.exe -NoExit -NoProfile -Command "& '%LLAMA_DIR%\llama-server.exe' -m '%MODEL%' --host 127.0.0.1 --port 8000 -c 2048 -np 1 --reasoning off --reasoning-budget 0"

echo Started llama-server on http://127.0.0.1:8000
echo A minimized PowerShell window keeps the server alive.
