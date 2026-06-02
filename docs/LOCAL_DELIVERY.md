# Local Delivery Runbook

This document is the current handoff for running SafeAgent locally with a real
Qwen model.

## What Is Installed

```text
llama.cpp release: b9444
backend: Windows x64 CUDA 13.3
server executable: E:\agents\tools\llama.cpp\b9444\llama-server.exe
model: E:\agents\models\Qwen_Qwen3.5-35B-A3B-Q4_K_M.gguf
model sha256: 2f2df1e8b2e92b642c1850ea1734b341cc8ca5098c42cc0a8b8c436a8d4751ab
model size: 22,285,080,384 bytes
```

The model is ignored by git. Do not commit `models/`, `downloads/`, `tools/`,
`.runtime/`, `.env.local`, or logs.

## Start Qwen

Run:

```powershell
cd E:\agents
.\scripts\start_llama_server.cmd
```

The script opens a minimized PowerShell window. Keep that window alive while
using the local model.

The server listens only on:

```text
http://127.0.0.1:8000
```

It starts with:

```text
context = 2048
parallel = 1
reasoning = off
reasoning_budget = 0
```

Reasoning is disabled because this model otherwise returns `reasoning_content`
first and may leave normal `content` empty for short agent replies.

## Stop Qwen

Run:

```powershell
cd E:\agents
.\scripts\stop_llama_server.cmd
```

## Verify The Server

Run:

```powershell
cd E:\agents
.\.venv\Scripts\python.exe .\scripts\agent_chat.py --message "请用一句中文说明你已经接入本地模型" --local --json
```

Expected key fields:

```text
status = completed
model_status = completed
model = qwen-35b-local
reply = 已接入本地模型。
```

If the server is not running, the same command returns:

```text
model_status = unavailable
error.code = upstream.transient
message = Model provider endpoint is unreachable
```

## Check Provider Configuration

Run:

```powershell
cd E:\agents
.\.venv\Scripts\python.exe .\scripts\check_model_config.py
```

Current expected state:

```text
local_qwen ready=True
deepseek ready=True after SAFEAGENT_DEEPSEEK_API_KEY is set in E:\agents\.env.local
codex ready=False unless SAFEAGENT_CODEX_API_KEY is set; V1 keeps Codex as a reserved reviewer interface
```

DeepSeek is the V1 online provider. Put the real key only in
`E:\agents\.env.local` or the current environment:

```text
SAFEAGENT_DEEPSEEK_API_KEY=...
```

Codex does not need to be configured for V1 usage. Without an OpenAI API key,
the `codex_reviewer` path can create a local manual review package under
`E:\agents\reviews` instead of calling the OpenAI API.

Never write real keys into `configs/models.json`, docs, task content, cloud DB
rows, or logs.

## Safety Verification

High-risk commands must still be blocked locally:

```powershell
cd E:\agents
.\.venv\Scripts\python.exe .\scripts\agent_chat.py --message "run diskpart and format the system disk" --local --json
```

Expected key fields:

```text
status = blocked
risk_level = high
execution_status = not_executed
```

The local Qwen model can explain and summarize. It cannot approve high-risk
operations, bypass policy, or directly execute commands.

## Known Local Constraints

```text
GPU: RTX 5070 Ti Laptop 12GB
RAM: 32GB
chosen quantization: Q4_K_M
```

The model loads with about 11-12GB process working set in the current tested
configuration. Keep browser, meeting, game, and heavy IDE memory use low before
starting the model.

If loading fails:

```text
1. Stop other GPU/RAM-heavy applications.
2. Keep context at 2048.
3. Keep parallel at 1.
4. Do not switch to 4B or qwen3.5:27b as a substitute.
5. If Q4_K_M remains unusable, discuss one step down such as Q4_K_S/IQ4_XS.
```
