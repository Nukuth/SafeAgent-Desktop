# SafeAgent V1 Handoff

This is the current usable checkpoint.

## What Works Now

```text
1. LangGraph runtime is active by default through SAFEAGENT_GRAPH_RUNTIME=auto.
2. DeepSeek is the V1 online model provider.
3. Local Qwen 35B remains available for emergency local chat when its server is running.
4. Codex has a reserved reviewer interface:
   - with SAFEAGENT_CODEX_API_KEY, it can call OpenAI Responses API;
   - without the key, codex_reviewer creates a manual review package under E:\agents\reviews.
5. The control console at http://127.0.0.1:8080 can submit tasks and refresh task/heartbeat status.
6. Execution remains gated. The graph runner and model output do not execute commands directly.
```

## Start The Control Console

```powershell
cd E:\agents
.\scripts\start_control_console.cmd
```

Open:

```text
http://127.0.0.1:8080
```

Use the `SAFEAGENT_SERVER_TOKEN` value from `E:\agents\.env.local` in the UI.
Do not paste DeepSeek, Codex, or Qwen model keys into the browser.

The home page now shows three startup blocks:

```text
1. 第一步：启动控制台服务
2. 第二步：启动本地 Worker
3. 第三步：打开页面并填 Token
```

The permission mode selector is shown in Chinese:

```text
提交任务（可创建和审批）
只审批（不能创建任务）
只读查看（不能提交或审批）
```

Only `提交任务（可创建和审批）` can create a new task. If the page is in
`只审批` or `只读查看`, the UI stops before calling the API and explains the
problem in Chinese instead of surfacing a raw validation error.

## Multi-Model View

The control console highlights the current model responsibilities:

```text
DeepSeek 主模型：普通规划、代码草案、命令草案、日志摘要。
Codex 高风险审查：高风险 diff、危险命令、批量文件操作审查；无 API key 时写 E:\agents\reviews。
本地 Qwen 35B 应急模型：断网或 API 不可用时本地对话，不能批准高风险执行。
```

## Watch Agent Process Logs

The control console now has a `过程日志` area.

```text
1. Submit a task. The page fills `Task ID` automatically.
2. Click `查看任务过程` to load the task event chain.
3. If the task has a run, the page fills `Run ID` automatically.
4. Click `查看 Run 过程` to inspect run-level events, approvals, and diagnostics.
```

The UI shows the redacted control-plane event stream only. It is meant for
watching which agent acted, what stage it reached, the risk level, network mode,
approval records, and short summaries.

Full local logs remain local:

```text
E:\agents\logs
```

Manual Codex review packages remain local:

```text
E:\agents\reviews
```

Useful API equivalents:

```text
GET /api/tasks/{task_id}
GET /api/runs/{run_id}
GET /api/devices/{device_id}/heartbeat
```

## Check Model Configuration

```powershell
cd E:\agents
.\.venv\Scripts\python.exe .\scripts\check_model_config.py
```

Expected V1 state after DeepSeek is configured:

```text
provider=deepseek enabled=True ready=True ... reason=ready
provider=codex enabled=True ready=False ... reason=missing SAFEAGENT_CODEX_API_KEY
```

Codex `ready=False` is acceptable for V1. It means automatic API review is not
configured. The manual review bridge remains available.

## Verify DeepSeek

```powershell
cd E:\agents
.\.venv\Scripts\python.exe .\scripts\probe_model_providers.py deepseek
.\.venv\Scripts\python.exe .\scripts\agent_chat.py --message "请用一句中文说明 DeepSeek 已接入 SafeAgent" --json
```

Expected evidence:

```text
OK deepseek: model=deepseek-chat ...
model_status = completed
model = deepseek-chat
status = completed
```

## Codex Reserved Interface

Automatic Codex review:

```text
SAFEAGENT_CODEX_API_KEY=your-openai-api-key
```

Manual Codex review without an API key:

```text
1. A high-risk graph path reaches codex_reviewer.
2. If the Codex provider is unavailable, SafeAgent writes:
   E:\agents\reviews\review_*.md
   E:\agents\reviews\review_*.json
3. Paste the markdown package into the current Codex conversation for review.
4. Do not treat the package itself as approval. Human approval is still required.
```

## Safety Boundaries

```text
1. DeepSeek/Codex/Qwen can propose or review, not execute.
2. Executor remains the only execution boundary.
3. High-risk actions are blocked or wait for local approval.
4. API keys stay in E:\agents\.env.local and are ignored by git.
5. Generated review packages stay in E:\agents\reviews and are ignored by git.
```

## Current Verification

Latest checkpoint verification:

```text
run_stdlib_tests.py: passed=159 failed=0
doctor.py: OK doctor checks
probe_model_providers.py deepseek: OK deepseek: model=deepseek-chat
probe_model_providers.py codex: SKIP codex: ready=False reason=missing SAFEAGENT_CODEX_API_KEY
agent_chat.py with DeepSeek: model_status=completed, model=deepseek-chat, status=completed
UI smoke: / returned 200, title found, Codex bridge text found, task create/list worked
UI process log smoke: / returned 200, process log section found, Agent event chain label found, open steps found
```

Run before relying on the checkpoint after future edits:

```powershell
cd E:\agents
.\.venv\Scripts\python.exe .\scripts\doctor.py
.\.venv\Scripts\python.exe .\scripts\run_stdlib_tests.py
```

Known non-blocking warnings:

```text
1. search_agent has network metadata but remains search-only.
2. remote profiles can reach executor only through approval gates.
3. research uses search_allowed network mode.
4. codex may be ready=False when SAFEAGENT_CODEX_API_KEY is not set.
```
