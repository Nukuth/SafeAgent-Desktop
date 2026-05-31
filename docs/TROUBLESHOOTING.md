# SafeAgent Workspace 报错处理手册

## 依赖缺失

### 现象

```text
ModuleNotFoundError: No module named 'fastapi'
ModuleNotFoundError: No module named 'pydantic'
ModuleNotFoundError: No module named 'httpx'
```

### 原因

项目依赖还没有安装到当前 Python 环境。

### 处理

```powershell
cd E:\agents
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .[dev]
```

如果下载失败，先检查网络，再考虑配置 PyPI 镜像。

## 认证失败

### 现象

API 返回：

```json
{
  "error": {
    "code": "auth.failed",
    "module": "shared.auth",
    "message": "Authentication failed"
  }
}
```

### 原因

请求没有带 `Authorization: Bearer <token>`，或者 token 与环境变量不一致。

### 处理

确认 server 环境变量：

```powershell
$env:SAFEAGENT_SERVER_TOKEN="change-me"
```

请求时使用：

```text
Authorization: Bearer change-me
```

## 远程权限不足

### 现象

API 返回：

```json
{
  "error": {
    "code": "auth.failed",
    "module": "shared.remote_permissions",
    "message": "Remote permission view_only cannot submit tasks"
  }
}
```

或：

```text
Remote permission view_only cannot approve tasks
New remote tasks must be created with submit_task permission
```

### 原因

远程请求的 `X-SafeAgent-Remote-Permission` 权限不允许当前操作。

当前规则：

```text
view_only：只能查看。
approval_only：可以 approval，不能 submit task。
submit_task：可以 submit task，也可以 approval。
```

### 处理

```text
1. 检查请求头 X-SafeAgent-Remote-Permission。
2. 提交任务必须是 submit_task。
3. 批准/拒绝任务必须是 approval_only 或 submit_task。
4. view_only 页面不要显示提交或批准按钮。
5. 不要通过修改 task body 的 remote_permission 绕过请求头权限。
```

## 任务没有被 worker 拉取

### 可能原因

```text
1. device_id 不一致。
2. worker token 与 server token 不一致。
3. server 没启动。
4. worker 没启动。
5. 任务状态已经不是 pending。
```

### 检查

```text
确认创建任务时的 device_id 与 worker 的 SAFEAGENT_DEVICE_ID 一致。
确认 SAFEAGENT_CONTROL_URL 指向正确 server。
查看 E:\agents\logs 下的本地日志。
```

## 高风险任务被拒绝

### 现象

worker 返回或记录：

```text
policy.denied
```

### 原因

策略引擎识别到删除、安装、下载后执行、外部路径写入、系统目录等风险。

### 处理

```text
这是预期安全行为。
先查看日志中的 risk_level 和 reason。
确认是否需要本地人工批准。
不要通过修改 server 绕过本地策略。
```

## unittest 显示 NO TESTS RAN

### 现象

```text
Ran 0 tests in 0.000s
NO TESTS RAN
```

### 原因

当前测试文件使用 pytest 风格函数，标准库 `unittest discover` 不会自动执行这些函数。

### 处理

使用项目提供的标准库测试入口：

```powershell
cd E:\agents
python .\scripts\run_stdlib_tests.py
```

如果已经安装 pytest，也可以运行：

```powershell
.\.venv\Scripts\pytest.exe
```

## worker 只 dry-run 不执行命令

### 现象

日志中出现：

```text
MVP completed policy-only dry run; no command execution performed
```

### 原因

当前是安全 MVP。Executor 尚未开放真实命令执行。

### 处理

这是预期行为。后续要先实现：

```text
1. 命令白名单
2. approval 读取
3. plan_hash 校验
4. expires_at 校验
5. 本地二次确认
```

再允许真实执行。

## 远程批准后仍然没有执行

### 现象

云端已经提交：

```text
decision = approved
```

但 worker 仍然返回：

```text
waiting_approval
rejected
```

或日志里出现：

```text
Approval rejected by local validation
```

### 原因

远程 approval 只是重新入队，不是直接执行。worker 会重新计算当前计划的 `plan_hash`，并检查：

```text
1. decision 必须是 approved。
2. approval.plan_hash 必须等于当前 plan_hash。
3. expires_at 必须存在。
4. expires_at 必须包含时区。
5. expires_at 必须尚未过期。
```

### 处理

```text
1. 查看 topology_router 或 policy_engine 事件中的 plan_hash。
2. 用这个 plan_hash 重新提交 approval。
3. expires_at 使用带时区的 ISO 时间。
4. 如果任务内容、profile、策略或 graph 变化，旧 approval 会失效，这是预期行为。
5. 当前 MVP 即使 approval 有效，也只 dry-run，不执行真实命令。
```

## 命令被执行器拒绝

### 现象

```text
policy.denied
Command proposal was denied by local validator
```

### 常见原因

```text
1. 命令不在只读 allowlist。
2. 命令在明确拒绝列表中，例如 Remove-Item、diskpart、fastboot、adb、curl。
3. cwd 不在 E:\agents 工作区下。
4. 策略引擎识别到删除、下载、安装或系统路径。
5. SAFEAGENT_EXECUTION_MODE 被设置成了非 dry_run。
```

### 当前 allowlist

```text
Get-ChildItem
Get-Item
Get-Content
Select-String
Test-Path
```

### 处理

```text
这是预期安全行为。
当前阶段不要把命令加入 allowlist 来绕过验证。
后续新增命令必须同时补充风险规则、approval 校验和测试。
```

## 误开启 live 执行模式

### 现象

日志或错误 details 中出现：

```text
execution_mode = live
unsupported execution_mode: live
```

### 原因

当前只支持：

```text
dry_run
live_readonly
```

`live` 不是合法 execution mode。

### 处理

```powershell
$env:SAFEAGENT_EXECUTION_MODE="dry_run"
```

然后重启 worker。

不要通过修改代码绕过这个限制。真实执行需要先补齐：

```text
1. command_hash 级 approval。
2. 命令超时。
3. stdout/stderr 截断和脱敏。
4. 退出码审计。
5. 文件变更备份和回滚策略。
```

## live_readonly 被拒绝

### 现象

日志或错误 details 中出现：

```text
live_readonly requires SAFEAGENT_ENABLE_LIVE_READONLY=true
command is not in live read-only allowlist
argument is unsafe for live execution
```

### 原因

`live_readonly` 是最小真实执行模式，只允许本机显式开启后的极小只读命令：

```text
Get-ChildItem
Get-Item
Test-Path
```

并且参数不能包含：

```text
; & | > < ` $ ( ) { }
```

### 处理

默认保持：

```powershell
$env:SAFEAGENT_EXECUTION_MODE="dry_run"
$env:SAFEAGENT_ENABLE_LIVE_READONLY="false"
```

如果本地确实要测试只读 live：

```powershell
$env:SAFEAGENT_EXECUTION_MODE="live_readonly"
$env:SAFEAGENT_ENABLE_LIVE_READONLY="true"
```

然后重新提交任务并完成 approval。`COMMAND_VALIDATED` 只做校验，真正执行只能发生在 approval 之后。

## 命令输出被截断或出现 [REDACTED]

### 现象

执行结果或日志里出现：

```text
[TRUNCATED]
[REDACTED]
output_audit.stdout_truncated = true
output_audit.stderr_truncated = true
```

### 原因

所有命令输出都会先经过本地输出审计：

```text
1. 先脱敏 token / api key / authorization 等敏感内容。
2. 再按字符数限制截断 stdout / stderr。
3. 在 output_audit 中记录原始长度和限制。
```

### 处理

默认限制：

```powershell
$env:SAFEAGENT_STDOUT_LIMIT_CHARS="4000"
$env:SAFEAGENT_STDERR_LIMIT_CHARS="4000"
```

如果需要临时提高限制，只能在本地 worker 环境变量中调整，并重启 worker。不要把未脱敏的大段输出回传云端。

## 输出限制配置错误

### 现象

```text
validation.failed
Output limit cannot be negative
```

### 原因

`SAFEAGENT_STDOUT_LIMIT_CHARS` 或 `SAFEAGENT_STDERR_LIMIT_CHARS` 被设置成负数。

### 处理

```powershell
$env:SAFEAGENT_STDOUT_LIMIT_CHARS="4000"
$env:SAFEAGENT_STDERR_LIMIT_CHARS="4000"
```

然后重启 worker。

## profile 引用了不存在的 agent

### 现象

```text
validation.failed
Profile <id> references unknown agents
```

### 原因

`configs/profiles.json` 的 `nodes` 中出现了没有在 `configs/agents.json` 注册的 agent。

### 处理

```text
1. 打开 configs/profiles.json。
2. 找到报错中的 profile。
3. 检查 nodes 列表。
4. 在 configs/agents.json 中补齐 agent，或从 profile 中移除该 node。
5. 同步更新 YAML 版本，保持人读配置和运行配置一致。
```

## agent/profile 安全契约失败

### 现象

启动 worker 或加载 registry 时出现：

```text
validation.failed
Only executor may have execute or write permissions
local_executor tool is reserved for executor
search_agent network access must be search_only without downloads
Profiles with executor must include approved human_approval edge
Profiles containing network-enabled agents must use search_allowed network mode
```

### 原因

`configs/agents.json` 或 `configs/profiles.json` 破坏了安全契约。

当前规则：

```text
1. 只有 executor 可以 can_execute=true 或 can_write=true。
2. local_executor 工具只能给 executor。
3. 默认只有 search_agent 可以联网。
4. search_agent 不能下载。
5. executor 前必须有 rule_reviewer / human_approval。
6. human_approval 到 executor 的边必须 condition=approved。
7. 联网 agent 只能出现在 search_allowed profile。
```

### 处理

```text
1. 不要为了启动成功直接放宽权限。
2. 先确认新增 agent 的 role、model_policy、tools、permissions、network 是否最小化。
3. 如果需要新增下载或写文件能力，应新增 profile 和策略测试，而不是直接改现有契约。
4. 修改 JSON 后同步 YAML。
5. 运行 python .\scripts\check_config_sync.py。
6. 运行 python .\scripts\doctor.py --quick。
7. 如果涉及执行、写入、联网或下载，再运行 python .\scripts\doctor.py。
```

如果你只是新增普通规划/审查 agent，先使用：

```text
permissions.can_execute = false
permissions.can_write = false
network.allowed = false
```

通过后再把它加入某个 profile 的 nodes/edges。

## YAML/JSON 配置不同步

### 现象

运行：

```powershell
python .\scripts\check_config_sync.py
```

看到：

```text
FAIL config YAML/JSON mismatch
```

### 原因

`configs/*.yaml` 和 `configs/*.json` 语义不一致。当前 worker 运行时读取 JSON，所以只改 YAML 不会生效。

### 处理

```text
1. 对比脚本输出的 yaml/json 文件名。
2. 确认你要保留哪一份配置。
3. 手动同步 YAML 和 JSON。
4. 再运行 python .\scripts\check_config_sync.py。
5. 再运行 python .\scripts\run_stdlib_tests.py。
```

如果配置格式超出内置 YAML 子集解析器能力，安装依赖后再检查：

```powershell
.\.venv\Scripts\python.exe -m pip install -e .[dev]
.\.venv\Scripts\python.exe .\scripts\check_config_sync.py
```

## 本地 smoke test 失败

### 现象

运行：

```powershell
python .\scripts\smoke_local_flow.py
```

看到：

```text
FAIL smoke_local_flow: ...
```

### 原因

本地闭环被破坏，常见位置包括：

```text
1. TaskStore claim/update/approval 行为变化。
2. LocalOrchestrator 不再对中风险任务返回 waiting_approval。
3. approval plan_hash 校验不稳定。
4. 高风险 diskpart 任务没有被 blocked。
5. registry/profile 安全契约加载失败。
```

### 处理

```text
1. 先运行 python .\scripts\check_config_sync.py。
2. 再运行 python .\scripts\run_stdlib_tests.py。
3. 查看失败断言文本，定位是 waiting_approval、completed、blocked 还是 plan_hash。
4. 不要通过放宽 PolicyEngine 或 approval 校验来让 smoke test 通过。
```

## doctor 自检失败

### 现象

运行：

```powershell
python .\scripts\doctor.py --quick
```

或：

```powershell
python .\scripts\doctor.py
```

看到：

```text
FAIL <check-name>
FAIL doctor checks
```

### 原因

doctor 是聚合入口，失败点会显示在 check 名称上：

```text
config_sync：配置不同步或 registry 安全契约失败。
module_boundaries：server/shared/local_worker import 边界被破坏。
local_smoke：本地任务/approval/policy 闭环失败。
compileall：Python 语法或导入编译失败。
stdlib_tests：标准库测试失败。
```

### 处理

```text
1. 先看第一个 FAIL 的 check 名称。
2. 单独运行对应脚本，例如 check_config_sync.py 或 smoke_local_flow.py。
3. 修复后再运行 python .\scripts\doctor.py --quick。
4. 提交前再运行 python .\scripts\doctor.py。
```

## module_boundaries 自检失败

### 现象

运行：

```powershell
python .\scripts\check_module_boundaries.py
```

或：

```powershell
python .\scripts\doctor.py --quick
```

看到：

```text
FAIL module boundaries
src/safeagent/server/xxx.py:1: module-boundary: safeagent.server.xxx must not import safeagent.local_worker.yyy
```

### 原因

某个模块越过了分层边界：

```text
shared 不能依赖 server 或 local_worker。
server 不能依赖 local_worker。
local_worker 不能依赖 server。
```

### 处理

```text
1. 不要为了通过检查把 import 移到函数内部绕过。
2. 如果 server 和 worker 都需要某个类型或函数，把它下沉到 safeagent.shared。
3. 如果 local_worker 需要和 server 通信，通过 client/API schema，不直接 import server.db 或 server.app。
4. 如果 server 需要展示 worker 结果，只读取已上传的 RunEvent/details，不调用 worker 模块。
5. 修复后运行 python .\scripts\check_module_boundaries.py。

## 单个远程任务失败，但 Worker 继续处理后续任务

这是预期的隔离行为。

本地 Worker 每次 polling 可能拿到多个 pending task。任何单个 task 在 approval
读取、LangGraph 编排、模型路由、策略检查、事件上报或状态更新阶段失败时，都不应让
同一批次的其他 task 被跳过。

排查步骤：

```powershell
Get-Content E:\agents\logs\worker.jsonl -Tail 80
```

重点看这些字段：

```text
event = task_failed
error.code = validation.failed / upstream.transient / worker.task_failed / worker.report_failed
error.module = 出错模块
task_id = 失败任务
run_id = 本地为失败边界生成的 run
```

如果看到：

```text
event = task_failure_report_failed
operation = post_event 或 update_status
```

说明本地已经捕获了任务失败，但向云端回传失败事件或失败状态时也遇到了网络/API
问题。此时不要重启整批任务，更不要绕过本地 policy；先检查控制台服务、token、网络
和 `/api/tasks/{task_id}/events` / `/api/tasks/{task_id}/status` 是否可用。

预期结果：

```text
1. 失败任务会尽量回传 run_failed 事件。
2. 失败任务会尽量更新为 failed。
3. 如果回传失败，本地日志仍保留 task_failed 和 task_failure_report_failed。
4. 同一轮 polling 中的后续任务继续处理。
```
6. 再运行 python .\scripts\doctor.py --quick。
```

## run diagnostics 显示异常状态

### 现象

查询：

```text
GET /api/runs/<run_id>
```

返回的 `diagnostics.status` 是：

```text
failed
blocked_or_skipped
waiting_approval
running_or_incomplete
not_found
```

### 原因

`diagnostics` 是从该 run 的 events 和 approvals 推导出来的摘要，不是另一个执行系统。

常见含义：

```text
failed：出现 run_failed 或 graph_node_failed 等错误事件。
blocked_or_skipped：执行被 policy、validator 或 approval 校验阻止。
waiting_approval：本地要求人工确认。
running_or_incomplete：已有事件，但还没有终态事件。
not_found：该 run_id 没有事件。
```

### 处理

```text
1. 先看 diagnostics.blocking_reasons。
2. 再看 diagnostics.errors。
3. 如果是 graph 分支问题，看 diagnostics.edge_decisions 和事件 details.edge_decisions。
4. 如果是 approval 问题，对照 plan_hash / command_hash / expires_at。
5. 如果是 not_found，确认 run_id 是否来自当前任务事件。
```

`diagnostics` 已脱敏。如果看到 `[REDACTED]`，说明原始事件里含有 token、API key 或类似敏感内容。

## task status 更新失败

### 现象

API 或本地 smoke 中出现：

```text
validation.failed
Cannot update status for unknown task
Invalid task status transition
```

### 原因

任务状态有明确生命周期，不能任意跳转。

允许的主要路径：

```text
pending -> claimed
claimed -> waiting_approval / completed / failed / blocked
waiting_approval -> pending / rejected
```

不允许：

```text
pending -> completed
completed -> pending
blocked -> claimed
failed -> pending
```

### 处理

```text
1. 查看错误 details.current_status 和 details.target_status。
2. 如果是 unknown task，确认 task_id 是否来自当前 server 数据库。
3. 如果需要 approval 后继续执行，应从 waiting_approval 变回 pending。
4. 不要通过直接改数据库绕过状态机。
5. 修复后运行 python .\scripts\smoke_local_flow.py。
```

## profile graph 编译失败

### 现象

```text
validation.failed
module = local_worker.graph_plan
```

### 常见原因

```text
1. entry 不在 nodes 中。
2. edge 的 from/to 指向了不存在的 node。
3. 某个 node 从 entry 无法到达。
4. graph 没有 terminal node。
```

### 处理

```text
1. 打开 configs/profiles.json。
2. 检查对应 profile 的 entry/nodes/edges。
3. 确保所有 nodes 至少有一条从 entry 可达的路径。
4. 修改 JSON 后同步 YAML。
5. 运行 python .\scripts\run_stdlib_tests.py 验证。
```

## profile edge condition 不支持

### 现象

启动 worker、运行配置检查或 doctor 时出现：

```text
validation.failed
Profile contains unsupported edge condition
```

### 原因

`configs/profiles.json` 或 `configs/profiles.yaml` 中的 edge condition 不在白名单里。

当前允许：

```text
low
medium
high
medium_or_higher
approved
review_passed
```

### 处理

```text
1. 打开报错 details.profile_id 对应的 profile。
2. 查看 details.invalid_conditions。
3. 把 condition 改成白名单中的值。
4. 如果确实需要新增 condition，先修改 safeagent.shared.graph_conditions。
5. 同步更新 GraphRunner 语义和测试。
6. 运行 python .\scripts\check_config_sync.py。
7. 运行 python .\scripts\doctor.py --quick。
```

## graph runner 节点失败

### 现象

```text
graph_node_failed
run_failed
```

### 原因

某个节点 handler 抛出了 `SafeAgentError` 或其它异常。

也可能是 profile edge 使用了未知 condition，例如：

```text
Unknown graph edge condition
```

### 处理

```text
1. 查看事件 details.node_results。
2. 查看事件 details.edge_decisions。
3. 找到 status = failed 的 node_id。
4. 查看 error.code、error.module、error.message。
5. 不要跳过失败节点继续执行后续 executor。
6. 修复节点 handler 或 profile 配置后重新运行。
```

当前 `GraphRunner` 会按 edge condition 保守遍历。不满足条件的分支不会执行；未知 condition 会返回 `validation.failed`，而不是猜测放行。

常见 condition：

```text
low
medium
high
medium_or_higher
approved
review_passed
```

如果某个 agent 没运行，先看 `edge_decisions`：

```text
selected=false, reason=risk_level=low
selected=false, reason=approval_valid=False
selected=false, reason=review_status=missing
```

这通常表示分支条件没有满足，不是模块崩溃。

## 模型 Provider 未配置

### 现象

```text
provider.not_configured
Model provider is not configured for deepseek
```

在 graph runner 事件里也可能表现为：

```text
model_status = unavailable
error.code = provider.not_configured
```

### 原因

当前 Model Router 已经能选择 DeepSeek/Codex 路由，但对应 provider adapter 没有被环境变量完整配置。

这是预期的隔离行为：节点会记录 provider 不可用，但不会因此让整个 GraphRunner 失败，也不会绕过本地 policy / approval / executor gate。

### 处理

```text
1. DeepSeek 至少需要 SAFEAGENT_DEEPSEEK_BASE_URL、SAFEAGENT_DEEPSEEK_MODEL、SAFEAGENT_DEEPSEEK_API_KEY。
2. Codex 至少需要 SAFEAGENT_CODEX_BASE_URL、SAFEAGENT_CODEX_MODEL、SAFEAGENT_CODEX_API_KEY。
3. 本地 Qwen 至少需要 SAFEAGENT_LOCAL_QWEN_BASE_URL、SAFEAGENT_LOCAL_QWEN_MODEL、SAFEAGENT_LOCAL_QWEN_API_KEY。
不要把 API Key 写入 configs 或云端数据库。
```

当前日志只允许记录：

```text
1. provider_id
2. base_url
3. model
4. has_api_key = true / false
5. timeout_seconds
```

如果日志中出现真实 API Key，这是安全缺陷，应立即停止 worker 并修复脱敏。

模型成功返回的 content 也会脱敏。如果你在节点输出里看到 `[REDACTED]`，优先假设模型复述了敏感内容，不要关闭脱敏。

## 模型节点输出 error 但任务没有失败

### 现象

GraphRunner 返回 completed，但某个 node output 中出现：

```text
model_status = unavailable
model_status = error
model.invocation_failed
```

### 原因

模型调用被设计成节点内部的可选能力。provider 未配置、网络不可达、上游超时、响应格式不兼容或未知异常，会被记录到节点输出中，而不是让整个图失败。

### 处理

```text
1. 先看 node_id，确认是 planner、producer、reviewer 还是 summarizer。
2. 看 error.code：provider.not_configured 通常是环境变量未配置。
3. 看 error.module：local_worker.providers 表示 provider adapter 层问题。
4. 不要为了消除该错误而把 API key 写进 configs 或云端数据库。
5. 如果只是离线/未配置模型，当前 dry-run 和 policy 检查仍可继续。
6. 如果该节点必须依赖模型结果，后续应在 profile 或 orchestrator 中显式声明 required_model，而不是让 provider 异常隐式中断其它模块。
```

## 模型服务返回格式不兼容

### 现象

```text
validation.failed
Model provider response does not match OpenAI-compatible chat format
```

### 原因

SafeAgent 当前 provider 期望响应格式兼容 OpenAI chat completions：

```text
choices[0].message.content
```

### 处理

```text
1. 确认服务地址是 /v1/chat/completions。
2. 确认本地 Qwen 服务开启了 OpenAI-compatible API。
3. 如果供应商格式不同，不要在业务节点里写临时解析逻辑；应该新增 provider adapter。
```

## 本地 Qwen 还没有部署

### 现象

开启：

```powershell
$env:SAFEAGENT_EMERGENCY_LOCAL_MODEL="true"
```

但本机没有启动任何 OpenAI-compatible 模型服务。

可能看到：

```text
upstream.transient
Local model endpoint is unreachable
```

### 原因

`SAFEAGENT_EMERGENCY_LOCAL_MODEL=true` 只表示 SafeAgent 会优先把普通推理路由到 `local_qwen`，不代表模型已经自动安装或自动启动。

### 处理

先完成一个低内存 35B/32B 级本地模型服务：

```text
1. 下载 35B/32B 级 GGUF 4-bit 模型。
2. 模型文件放到 E:\agents\models。
3. 用 llama.cpp / llama-server / LM Studio / Ollama 暴露 OpenAI-compatible API。
4. 确认 API base URL 是 http://127.0.0.1:8000/v1 或同步修改环境变量。
5. 再启动 SafeAgent worker。
```

## 本地 Qwen 内存不足或非常慢

### 现象

```text
模型加载失败
系统内存占用过高
首 token 等待很久
电脑明显卡顿
```

### 处理

```text
1. 确认使用 GGUF Q4_K_M，而不是 FP16。
2. 如果仍然加载失败，改用 Q3_K_M 或 Q2_K。
3. 把上下文从 32768 降到 4096。
4. 并发设为 1。
5. 关闭不必要的浏览器、IDE、游戏和后台服务。
6. 仍然不行时，先用 7B/8B 验证 API，再回到 35B/32B 排查模型文件或参数。
7. 不要让本地模型参与高风险审查，避免慢模型阻塞安全流程。
```

## 日志里出现 [REDACTED]

### 原因

系统检测到 token、secret、password、authorization 等敏感字段并自动脱敏。

### 处理

这是预期行为。不要为了调试而关闭脱敏；如果需要排查，只在本地临时、安全地检查原始配置。
