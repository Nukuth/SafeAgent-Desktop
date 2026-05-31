# SafeAgent Workspace 使用方法

## 当前状态

当前是 MVP 骨架阶段，已经包含：

```text
1. 共享 schema / error / audit log
2. 云端控制平面 API 草案
3. SQLite 任务队列
4. 本地 Policy Engine
5. 本地 polling worker
6. dry-run Orchestrator
7. 标准库测试脚本
8. 报错处理手册
9. 构建日志
```

当前 Executor 仍然是 dry-run，不会执行真实命令。

## 安装依赖

```powershell
cd E:\agents
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .[dev]
```

## 本地私密环境变量

本地长期使用的 token 和模型 API Key 可以放在：

```text
E:\agents\.env.local
```

这个文件已被 `.gitignore` 忽略，不应提交。格式是简单的 `KEY=VALUE`：

```text
SAFEAGENT_WORKER_TOKEN=replace-with-long-random-token
SAFEAGENT_DEEPSEEK_API_KEY=你的 DeepSeek API Key
SAFEAGENT_LOCAL_QWEN_API_KEY=local-no-key
```

加载优先级：

```text
1. 先读取 .env.local。
2. 再叠加当前 PowerShell 环境变量。
3. 如果两边都有同名 key，当前 PowerShell 环境变量优先。
```

如果 `.env.local` 不在默认位置，可以设置：

```powershell
$env:SAFEAGENT_ENV_FILE="E:\agents\.env.local"
```

检查模型 key 是否已被识别：

```powershell
.\.venv\Scripts\python.exe .\scripts\check_model_config.py
```

## 启动云端控制平面

本地测试：

```powershell
cd E:\agents
$env:SAFEAGENT_SERVER_TOKEN="change-me"
$env:SAFEAGENT_DB_PATH="E:\agents\state\server.sqlite3"
.\.venv\Scripts\uvicorn.exe safeagent.server.app:create_app --factory --host 127.0.0.1 --port 8080
```

## 创建任务

示例请求：

```powershell
$headers = @{ Authorization = "Bearer change-me" }
$body = @{
  content = "检查 E:\agents 当前项目状态并总结"
  device_id = "local-pc-1"
  requested_profile = "safe_shell"
  remote_permission = "submit_task"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8080/api/tasks" -Headers $headers -Body $body -ContentType "application/json"
```

远程权限头：

```powershell
$headers = @{
  Authorization = "Bearer change-me"
  "X-SafeAgent-Remote-Permission" = "submit_task"
}
```

权限含义：

```text
view_only：只能查看 run/task 状态。
approval_only：可以批准或拒绝已有计划，不能提交新任务。
submit_task：可以提交新任务，也可以批准已有计划。
```

为了兼容本地 MVP，未传 `X-SafeAgent-Remote-Permission` 时按 `submit_task` 处理。远程 UI 接入时应显式传入权限头。

## 查看待处理任务

```powershell
$headers = @{ Authorization = "Bearer change-me" }
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8080/api/tasks/pending?device_id=local-pc-1" -Headers $headers
```

Worker 专用接口应使用 `SAFEAGENT_WORKER_TOKEN`，不要用远程 UI 的
`SAFEAGENT_SERVER_TOKEN`：

```powershell
$workerHeaders = @{ Authorization = "Bearer worker-token" }
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8080/api/tasks/pending?device_id=local-pc-1" -Headers $workerHeaders
```

远程控制台 token 只能用于提交任务、读取 run、记录人工 approval。以下接口属于本地
worker 专用：

```text
GET  /api/tasks/pending
POST /api/tasks/{task_id}/heartbeat
POST /api/tasks/{task_id}/events
GET  /api/tasks/{task_id}/approval/latest
POST /api/tasks/{task_id}/status
```

远程 UI 的只读任务状态接口使用 `SAFEAGENT_SERVER_TOKEN`，不会 claim 任务，也不会改变任务状态：

```powershell
$headers = @{ Authorization = "Bearer change-me" }
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8080/api/tasks?device_id=local-pc-1" -Headers $headers
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8080/api/tasks?device_id=local-pc-1&status=waiting_approval" -Headers $headers
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8080/api/tasks/<task_id>" -Headers $headers
```

返回内容只来自云端控制面数据库里的脱敏任务、事件和 approval：

```text
GET /api/tasks:
tasks
filters
limit

GET /api/tasks/{task_id}:
task
events
approvals
run_ids
```

如果需要某个 run 的诊断摘要，再用 `GET /api/runs/{run_id}`。不要让远程 UI 调
`GET /api/tasks/pending`，那个接口属于本地 worker，会把 pending 任务改成 claimed。

正式远程部署时，`SAFEAGENT_SERVER_TOKEN` 和 `SAFEAGENT_WORKER_TOKEN` 应不同。

## 重要安全提醒

```text
1. 云端只负责排队、审批和展示，不负责执行。
2. 本地 worker 必须重新做风险判断。
3. 不要把 DeepSeek / Codex API Key 写入云端数据库。
4. 不要让云端直接下发裸命令执行。
5. 外部路径写入、删除、安装、下载执行必须提高风险等级。
```

## 不安装依赖时的核心验证

当前部分核心模块只依赖 Python 标准库，可以直接运行：

```powershell
cd E:\agents
python .\scripts\run_stdlib_tests.py
```

通过时应看到：

```text
passed=19 failed=0
```

## 项目 Doctor 自检

平时修改代码或配置后，优先运行：

```powershell
cd E:\agents
python .\scripts\doctor.py --quick
```

`--quick` 会检查：

```text
1. YAML/JSON 配置同步。
2. registry 安全契约。
3. 本地闭环 smoke test。
4. compileall。
```

完整自检：

```powershell
python .\scripts\doctor.py
```

完整自检会额外运行：

```text
python .\scripts\run_stdlib_tests.py
```

通过时最后会看到：

```text
OK doctor checks
```

## 启动本地 Worker

安装依赖后：

```powershell
cd E:\agents
$env:SAFEAGENT_CONTROL_URL="http://127.0.0.1:8080"
$env:SAFEAGENT_WORKER_TOKEN="change-me"
$env:SAFEAGENT_DEVICE_ID="local-pc-1"
$env:SAFEAGENT_WORKSPACE_ROOT="E:\agents"
.\.venv\Scripts\python.exe -m safeagent.local_worker.worker
```

worker 会：

```text
1. 拉取 pending task。
2. 本地选择 profile。
3. 本地 Policy Engine 判断风险。
4. 写入 E:\agents\logs\worker.jsonl。
5. 回传脱敏事件到 server。
6. 不执行真实命令。
```

## 当前命令执行边界

当前系统已经有命令提案和执行器接口，但仍然是 dry-run。

允许进入 dry-run 校验的只读命令：

```text
Get-ChildItem
Get-Item
Get-Content
Select-String
Test-Path
```

明确拒绝：

```text
Remove-Item
del
rmdir
diskpart
format
bcdedit
bootrec
reg
fastboot
adb
Invoke-WebRequest
curl
Start-Process
```

所有真实执行能力必须等后续补齐：

```text
1. approval 读取
2. plan_hash 校验
3. expires_at 校验
4. 本地二次确认
5. 命令级审计日志
```

当前已经补齐的执行前 gate：

```text
1. 每条 CommandProposal 都会生成 command_hash。
2. command_hash 会进入 plan_hash。
3. approval 通过时会同时记录 plan_hash 和 command_hash。
4. SAFEAGENT_EXECUTION_MODE 默认是 dry_run。
5. 只支持 dry_run 和 live_readonly 两种 execution_mode。
6. live_readonly 默认关闭，必须显式设置 SAFEAGENT_ENABLE_LIVE_READONLY=true。
7. live_readonly 即使开启，也必须先通过 approval。
8. live_readonly 只允许极小只读子集：Get-ChildItem / Get-Item / Test-Path。
9. live_readonly 参数会拒绝 ; & | > < ` $ ( ) { } 等高风险字符。
10. stdout / stderr 会先脱敏再截断。
11. ExecutionResult 会记录 timeout_seconds 和 output_audit。
```

环境变量：

```powershell
$env:SAFEAGENT_EXECUTION_MODE="dry_run"
$env:SAFEAGENT_EXECUTION_TIMEOUT_SECONDS="30"
$env:SAFEAGENT_STDOUT_LIMIT_CHARS="4000"
$env:SAFEAGENT_STDERR_LIMIT_CHARS="4000"
$env:SAFEAGENT_ENABLE_LIVE_READONLY="false"
```

当前默认不要开启 live-readonly。若后续本地临时测试，只能使用：

```powershell
$env:SAFEAGENT_EXECUTION_MODE="live_readonly"
$env:SAFEAGENT_ENABLE_LIVE_READONLY="true"
```

并且仍然需要有效 approval。

后续真的开放更完整真实执行时，必须先补：

```text
1. command_hash 级 approval。
2. 真实进程超时强制终止。
3. stdout/stderr 大输出落盘策略。
4. 进程退出码审计。
5. 可回滚操作的备份记录。
```

## Approval 和 plan_hash

当前设计中，批准必须绑定具体计划：

```text
plan_hash = sha256(canonical_json(plan))
```

一个 approval 至少应包含：

```text
decision = approved / rejected
approval_scope = plan_only
plan_hash = 当前计划 hash
expires_at = 带时区的 ISO 时间
```

如果计划内容变化、hash 不一致、approval 过期或 decision 不是 approved，本地 worker 后续必须拒绝执行。

`plan_hash` 当前包含：

```text
1. task_id
2. content
3. profile
4. graph
5. network_mode
6. policy
7. model_route
8. execution_mode
9. live_readonly_enabled
10. execution_requires_approval
11. command
12. command_hash
```

远程 approval 的语义：

```text
1. 云端记录 approval。
2. 如果 decision=approved，任务状态重新变为 pending。
3. 本地 worker 再次拉取任务。
4. 本地重新计算 plan_hash。
5. 本地读取最新 approval。
6. 本地校验 decision / plan_hash / expires_at。
7. 校验通过后才允许进入后续步骤。
```

这意味着：

```text
远程批准不是执行权限。
远程批准只是允许本地 worker 重新评估同一个计划。
```

当前 MVP 即使 approval 有效，仍然只完成 dry-run，不执行真实命令。

## Agent/Profile Registry

当前有两套配置：

```text
configs/agents.yaml      给人阅读和编辑
configs/profiles.yaml    给人阅读和编辑
configs/agents.json      当前运行时加载
configs/profiles.json    当前运行时加载
```

现在运行时优先使用 JSON，是为了在没安装 PyYAML 时也能启动核心 worker。

Agent 安全契约：

```text
1. 只有 executor 可以 can_execute=true 或 can_write=true。
2. local_executor 工具只能给 executor。
3. 默认只有 search_agent 可以 network.allowed=true。
4. search_agent 必须是 search_only，且 can_download=false。
5. codex_review model_policy 只能给 codex_reviewer。
6. human_approval 不能调用模型，model_policy 必须是 none。
```

Profile 安全契约：

```text
1. 包含 executor 的 profile 必须包含 rule_reviewer 和 human_approval。
2. executor 必须有 human_approval -> executor 且 condition=approved 的边。
3. executor 只能从 rule_reviewer 或 human_approval 到达。
4. 包含 codex_reviewer 的 profile 必须包含 rule_reviewer 和 human_approval。
5. 包含联网 agent 的 profile 必须使用 search_allowed network_mode。
6. search_allowed profile 必须包含 search_agent。
```

这些规则在 registry 加载时就会检查。配置不符合时，worker 会直接启动失败，而不是运行到任务中途再失败。

如果 profile 引用了不存在的 agent，会报：

```text
validation.failed
module = local_worker.registry
message = Profile <id> references unknown agents
```

处理方式：

```text
1. 检查 configs/profiles.json 的 nodes。
2. 确认每个 node 都在 configs/agents.json 的 agents 下声明。
3. YAML 和 JSON 需要保持一致。
```

## 自主调整 agent 关系和权限

可以自主调整：

```text
1. 新增普通 agent。
2. 调整 agent 的 role、model_policy、tools。
3. 调整 profile 的 nodes。
4. 调整 profile 的 edges 顺序和 condition。
5. 新增只读、只规划、只审查类 profile。
6. 决定某个 profile 是否 remote_allowed。
```

默认新增 agent 建议从最小权限开始：

```json
{
  "role": "producer",
  "model_policy": "deepseek_default",
  "tools": [],
  "permissions": {"can_execute": false, "can_write": false},
  "network": {"allowed": false}
}
```

不要直接放开的权限：

```text
1. 不要把 can_execute=true 给 executor 以外的 agent。
2. 不要把 can_write=true 给 executor 以外的 agent。
3. 不要把 local_executor 给 executor 以外的 agent。
4. 不要让普通 agent 默认联网。
5. 不要让 search_agent 下载文件。
6. 不要让 human_approval 调用模型。
7. 不要让 executor 绕过 rule_reviewer / human_approval。
```

每次改完配置后必须运行：

```powershell
cd E:\agents
python .\scripts\check_config_sync.py
python .\scripts\doctor.py --quick
```

如果涉及执行、写入、联网、下载、Codex 审查路径，还要补测试后运行：

```powershell
python .\scripts\doctor.py
```

## 配置同步检查

运行时当前读取：

```text
configs/agents.json
configs/profiles.json
```

给人阅读和编辑的版本是：

```text
configs/agents.yaml
configs/profiles.yaml
```

修改配置后运行：

```powershell
cd E:\agents
python .\scripts\check_config_sync.py
```

通过时应看到：

```text
OK config YAML/JSON sync and registry security contracts
```

这个脚本会检查：

```text
1. YAML 和 JSON 语义是否一致。
2. registry 是否能加载。
3. agent/profile 安全契约是否通过。
```

如果没有安装 PyYAML，脚本会使用项目内置的保守 YAML 子集解析器。该解析器只支持当前配置文件使用的格式，不适合作为通用 YAML 解析器。

## 模块边界检查

运行：

```powershell
cd E:\agents
python .\scripts\check_module_boundaries.py
```

通过时应看到：

```text
OK module boundaries
```

当前硬边界：

```text
1. safeagent.shared 不能 import safeagent.server。
2. safeagent.shared 不能 import safeagent.local_worker。
3. safeagent.server 不能 import safeagent.local_worker。
4. safeagent.local_worker 不能 import safeagent.server。
```

原因：

```text
shared：只放 schema、错误、脱敏、诊断等低层公共能力。
server：只做控制平面和队列，不知道本地执行细节。
local_worker：只做本地执行/审查/模型路由，不反向依赖云端实现。
```

`python .\scripts\doctor.py --quick` 和完整 `doctor.py` 都会自动运行这个检查。

## Run Diagnostics

查询 run：

```powershell
$headers = @{ Authorization = "Bearer change-me" }
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8080/api/runs/<run_id>" -Headers $headers
```

返回结构包含：

```text
events：完整脱敏事件列表。
approvals：该 run 的 approval 记录。
diagnostics：从 events/approvals 推导出的稳定诊断摘要。
```

`diagnostics` 主要字段：

```text
status：completed / failed / blocked_or_skipped / waiting_approval / running_or_incomplete / not_found
event_count：事件数量
approval_count：approval 数量
agents：参与过的 agent
risk_level：本次 run 出现过的最高风险等级
network_modes：出现过的网络模式
event_type_counts：事件类型计数
error_count：错误事件数量
errors：错误摘要
blocking_reasons：阻塞或等待审批原因
edge_decisions：graph edge selected/skipped/failed 统计
```

这个摘要只从已上传的脱敏事件生成，不读取本地完整日志，也不包含模型 API Key。

## Task Status Lifecycle

任务状态不是任意可改的。`TaskStore.update_task_status()` 会检查状态转换：

```text
pending -> claimed
pending -> rejected
claimed -> running / waiting_approval / completed / failed / blocked / rejected
running -> waiting_approval / completed / failed / blocked / rejected
waiting_approval -> pending / rejected
completed / failed / blocked / rejected -> 终态，不允许回滚
```

常见流程：

```text
pending
-> claimed
-> waiting_approval
-> pending   远程 approval 后重新入队
-> claimed
-> completed / blocked / failed
```

如果直接把 `pending` 改成 `completed`，或把 `completed` 改回 `pending`，会返回 `validation.failed`。

## 本地闭环 Smoke Test

不启动 FastAPI、不安装额外依赖时，可以运行：

```powershell
cd E:\agents
python .\scripts\smoke_local_flow.py
```

通过时应看到：

```text
OK local smoke flow
medium_status=completed
high_status=blocked
```

该脚本会模拟：

```text
1. SQLite TaskStore 创建中风险任务。
2. worker claim pending task。
3. LocalOrchestrator 返回 waiting_approval。
4. 记录 approval，任务重新入队。
5. worker 再次 claim，并用 approval 完成 dry-run。
6. 创建高风险 diskpart 任务。
7. 本地策略将高风险任务 blocked。
8. 验证事件已写入本地 store。
```

它适合在改动 orchestrator、approval、policy、registry、store 后做快速回归。

## Profile Graph Plan

`configs/profiles.json` 中每个 profile 现在包含：

```text
entry：入口节点
nodes：允许参与该 profile 的节点
edges：节点之间的连接和条件
```

示例：

```json
{"from": "rule_reviewer", "to": "human_approval", "condition": "medium_or_higher"}
```

启动 worker 时，profile 会被编译成 GraphPlan。GraphPlan 会检查：

```text
1. entry 必须在 nodes 中。
2. edges 的 from/to 必须都在 nodes 中。
3. 所有 nodes 必须能从 entry 到达。
4. graph 必须至少有一个 terminal node。
```

GraphPlan 会进入 plan_hash，所以 profile 拓扑变化后，旧 approval 会自动失效。

## GraphRunner

当前项目包含一个标准库版 `GraphRunner`。

它的作用：

```text
1. 从 GraphPlan.entry 开始，按 edges 和 condition 生成可审计 trace。
2. 捕获节点级错误并转换为 ErrorEnvelope。
3. 在未安装 LangGraph 前验证图执行语义。
4. 为后续 LangGraph StateGraph 适配提供稳定输入输出。
```

当前支持的 edge condition：

```text
low：仅 low 风险通过。
medium：仅 medium 风险通过。
high：high / extreme 风险通过。
medium_or_higher：medium / high / extreme 风险通过。
approved：只有 GraphState.payload.approval_valid=true 才通过。
review_passed：只有上游节点 output.review_status=passed 才通过。
```

这些 condition 由 `safeagent.shared.graph_conditions` 统一定义。Registry 加载 profile 时会先校验 condition，写错会在配置阶段失败，而不是等任务运行到 GraphRunner 才失败。

保守规则：

```text
1. 未知 condition 会让 graph_runner 返回 validation.failed。
2. placeholder reviewer 不会被当作 review_passed。
3. 没有有效 approval 时，human_approval 后不会进入 executor。
4. 不满足条件的分支不会运行，避免无关 agent 干扰本次任务。
```

GraphRunResult 会同时返回：

```text
node_results：实际运行过的节点。
edge_decisions：每条已评估 edge 的 selected=true/false 和 reason。
```

`edge_decisions` 用来排查“为什么某个 agent 没运行”：

```text
selected=false, reason=risk_level=low
selected=false, reason=approval_valid=False
selected=false, reason=review_status=missing
```

它不会：

```text
1. 执行 shell。
2. 访问网络。
3. 写文件。
4. 调用 server。
```

如果节点失败，当前 graph 会停止，并产生结构化失败结果。

## 框架路线

项目长期核心仍然是：

```text
LangGraph
```

当前 MVP 先实现了一个标准库 `GraphRunner`，不是为了替代 LangGraph，而是为了先稳定这些边界：

```text
1. profile graph 的 entry/nodes/edges 校验。
2. 节点失败时的 ErrorEnvelope。
3. plan_hash 的稳定输入。
4. 审批、风险、执行、日志之间的模块边界。
5. 不依赖第三方包时也能跑核心测试。
```

后续迁移方式：

```text
configs/profiles.json
→ GraphPlan
→ LangGraph StateGraph
→ interrupt() 人工确认
→ checkpointer 持久化
```

原则：

```text
1. UI 不承担核心安全控制。
2. 模型 provider 不承担执行权。
3. LangGraph 负责状态、分支、审批暂停和恢复。
4. 本地 PolicyEngine / Executor 负责最终安全边界。
```

## Node Handlers

节点 handler 位于：

```text
src/safeagent/local_worker/node_handlers.py
```

当前 handler 是安全占位实现：

```text
planner：生成结构化目标
shell_agent：只生成命令提案类型说明
file_agent：只生成文件整理计划类型说明
code_agent：只生成 patch 计划类型说明
search_agent：只生成搜索计划类型说明，不联网
reviewer：只记录审查边界
human_approval：不处理真实批准
executor：不执行命令
summarizer：生成占位总结
```

约束：

```text
1. handler 不直接调用 server。
2. handler 不直接执行 shell。
3. handler 不直接访问网络。
4. handler 不直接写文件。
5. handler 后续如需副作用，必须通过 PolicyEngine / Executor / approval gate。
```

模型调用边界：

```text
1. handler 可以通过 ProviderModelInvoker 调用 provider。
2. provider 未配置、不可达、返回格式错误或抛出 SafeAgentError 时，只记录到当前 node output。
3. provider 未知异常会转成 model.invocation_failed。
4. 模型成功 content 和错误输出都会脱敏。
5. 模型失败不会让 GraphRunner 失败，也不会跳过 policy / approval / executor gate。
6. human_approval 和 executor 不调用模型。
```

节点模型状态：

```text
skipped：该节点没有模型调用，或没有注入 provider registry。
completed：模型调用成功，返回 content 和 usage。
unavailable：provider 未配置、上游不可达、响应不兼容或 SafeAgentError。
error：provider 出现未知异常，已转成结构化错误。
```

## Model Provider 未配置

模型端点和模型名配置在：

```text
configs/models.json
configs/models.yaml
```

真实 API Key 不写入配置文件，只从本地环境变量读取。当前默认配置：

```text
local_qwen:
  base_url = http://127.0.0.1:8000/v1
  model = qwen-35b-local
  api_key_env = SAFEAGENT_LOCAL_QWEN_API_KEY

deepseek:
  base_url = https://api.deepseek.com/v1
  model = deepseek-chat
  api_key_env = SAFEAGENT_DEEPSEEK_API_KEY

codex:
  默认 disabled
  api_key_env = SAFEAGENT_CODEX_API_KEY
```

如果直接调用 NullProvider，会报：

```text
provider.not_configured
module = local_worker.providers
```

这是预期行为，通常表示 `configs/models.json` 里对应 provider 未启用、base_url/model 为空，或者本地没有设置对应
API Key 环境变量。节点 handler 会把错误写入对应节点的 `model` 字段，`GraphRunner` 仍会继续完成 trace，不会绕过
policy / approval / executor gate。

检查当前模型配置状态：

```powershell
.\.venv\Scripts\python.exe .\scripts\check_model_config.py
```

输出只包含 `has_api_key=true/false` 和 `api_key_source`，不会打印真实 API Key。典型输出含义：

```text
ready=True：配置足够，worker 可以构建该 provider。
ready=False reason=missing SAFEAGENT_DEEPSEEK_API_KEY：本地还没设置 DeepSeek key。
reason=provider disabled in config：该 provider 在 configs/models.json 里关闭。
```

## 本地 Qwen 应急模型

本地 Qwen 的详细使用方式见：

```text
docs/LOCAL_QWEN.md
```

最小环境变量：

```powershell
$env:SAFEAGENT_EMERGENCY_LOCAL_MODEL="true"
$env:SAFEAGENT_LOCAL_QWEN_API_KEY="local-no-key"
```

`base_url` 和 `model` 在 `configs/models.json` 的 `local_qwen` 下配置。开启后，普通任务会优先路由到
`local_qwen`。高风险任务仍不能由本地模型批准。

本地模型主路线改为直接上 35B/32B 级 GGUF 4-bit 量化：

```text
1. 模型文件放到 E:\agents\models。
2. 用 llama.cpp / llama-server / LM Studio / Ollama 暴露 OpenAI-compatible API。
3. API base URL 保持 http://127.0.0.1:8000/v1。
4. 量化优先 Q4_K_M；内存不足时退到 Q3_K_M 或 Q2_K。
5. 上下文先设 4096，稳定后再提高。
6. 并发先设 1。
7. 小模型只作为排障 fallback，不作为主路线。
```
## 查看 Worker 心跳

本地 worker 每次 polling 前后都会尽力上报 heartbeat。远程 UI 使用
`SAFEAGENT_SERVER_TOKEN` 读取，不需要持有 worker token：

```powershell
$headers = @{ Authorization = "Bearer change-me" }
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8080/api/devices/local-pc-1/heartbeat" -Headers $headers
```

返回中重点看：

```text
device_id
device_status
age_seconds
stale_after_seconds
heartbeat.device_id
heartbeat.phase
heartbeat.status
heartbeat.task_count
heartbeat.updated_at
```

`device_status` 由控制面根据 `heartbeat.updated_at` 派生，不需要 UI 自己猜：

```text
online：最近 60 秒内有 heartbeat。
stale：曾经有 heartbeat，但已经超过 stale_after_seconds。
never_seen：该 device_id 从未成功上报 heartbeat。
```

可以通过查询参数临时调整过期阈值：

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8080/api/devices/local-pc-1/heartbeat?stale_after_seconds=120" -Headers $headers
```

如果 `device_status = never_seen`，表示该 `device_id` 还没有成功上报过心跳。先检查
`SAFEAGENT_DEVICE_ID`、`SAFEAGENT_WORKER_TOKEN` 和 worker 是否正在运行。
