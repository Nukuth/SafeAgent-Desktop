# SafeAgent Workspace 构建日志

## 2026-05-29

### 目标

开始构建安全优先的本地多智能体系统 MVP。当前阶段重点不是完整智能体能力，而是先打好模块边界：

```text
云端控制平面
本地 worker
共享 schema
统一错误模型
审计日志
策略引擎
清晰报错机制
```

### 已完成步骤

1. 检查 `E:\agents` 当前状态。
   - 发现已有研究文档：
     - `framework_integration_decision.md`
     - `multi_agent_architecture_research.md`
     - `multi_agent_research_reference_map.md`

2. 创建项目基础文件。
   - `pyproject.toml`
   - `README.md`
   - `.env.example`
   - `src/safeagent/...`

3. 创建共享模块。
   - `src/safeagent/shared/enums.py`
   - `src/safeagent/shared/errors.py`
   - `src/safeagent/shared/auth.py`
   - `src/safeagent/shared/ids.py`
   - `src/safeagent/shared/time.py`
   - `src/safeagent/shared/redaction.py`
   - `src/safeagent/shared/schemas.py`
   - `src/safeagent/shared/audit_log.py`

4. 创建云端控制平面模块。
   - `src/safeagent/server/settings.py`
   - `src/safeagent/server/db.py`
   - `src/safeagent/server/app.py`

5. 创建本地 worker MVP。
   - `src/safeagent/local_worker/settings.py`
   - `src/safeagent/local_worker/policy.py`
   - `src/safeagent/local_worker/orchestrator.py`
   - `src/safeagent/local_worker/client.py`
   - `src/safeagent/local_worker/worker.py`

6. 创建 agent/profile 配置草案。
   - `configs/agents.yaml`
   - `configs/profiles.yaml`

7. 创建测试。
   - `tests/test_shared.py`
   - `tests/test_policy.py`
   - `tests/test_orchestrator.py`
   - `scripts/run_stdlib_tests.py`

8. 补齐 approval 与 plan_hash 基础。
   - `src/safeagent/shared/plan_hash.py`
   - `src/safeagent/shared/approval.py`
   - `TaskStore.latest_approval()`
   - worker 状态回传到 `/api/tasks/{task_id}/status`

9. 添加模块隔离测试。
   - `tests/test_module_boundaries.py`
   - 确保 server 不导入 local_worker。
   - 确保 shared 不导入 server/local_worker。

10. 添加运行时 registry 和模型路由边界。
    - `configs/agents.json`
    - `configs/profiles.json`
    - `src/safeagent/local_worker/registry.py`
    - `src/safeagent/local_worker/model_router.py`
    - `src/safeagent/local_worker/providers.py`
    - `tests/test_registry.py`
    - `tests/test_model_router.py`

11. 添加命令提案和 dry-run 执行器边界。
    - `src/safeagent/local_worker/executor.py`
    - `tests/test_executor.py`
    - orchestrator 现在会输出 `command_proposed` 和 `command_validated` 事件。

12. 添加 profile graph plan 编译层。
    - `src/safeagent/local_worker/graph_plan.py`
    - `tests/test_graph_plan.py`
    - `configs/profiles.json` 增加 `entry` 和 `edges`
    - orchestrator 将 graph plan 纳入 `plan_hash`

13. 添加标准库版 graph runner。
    - `src/safeagent/local_worker/graph_runner.py`
    - `tests/test_graph_runner.py`
    - `GraphRunner` 只运行占位节点 handler，不调用模型、工具、shell、server。
    - 节点异常会被转换为结构化 `ErrorEnvelope`，并停止当前 graph。

14. 添加默认节点 handler 注册表。
    - `src/safeagent/local_worker/node_handlers.py`
    - `tests/test_node_handlers.py`
    - handler 覆盖所有 `configs/agents.json` 中声明的 agent。
    - handler 只输出结构化占位结果，不调用外部副作用。

15. 增加本地 Qwen 35B 应急模型支持。
    - `SAFEAGENT_EMERGENCY_LOCAL_MODEL`
    - `SAFEAGENT_LOCAL_QWEN_BASE_URL`
    - `SAFEAGENT_LOCAL_QWEN_MODEL`
    - `SAFEAGENT_LOCAL_QWEN_API_KEY`
    - `OpenAICompatibleLocalProvider`
    - `docs/LOCAL_QWEN.md`

### 当前设计决策

```text
1. 云端 server 不导入 local_worker 模块。
2. local_worker 后续只能通过 shared schema 与 server 通信。
3. 所有公开 ID 使用 UUID 前缀，不使用自增 ID。
4. 错误统一使用 ErrorEnvelope。
5. 云端只保存脱敏事件和任务状态，不保存 API Key。
6. 本地完整日志后续写入 E:\agents\logs。
7. 当前 Executor 是 dry-run，不执行真实命令。
8. 高风险任务直接 blocked，中风险任务 waiting_approval。
9. approval 必须绑定 plan_hash 和 expires_at。
10. server 可以记录 approval，但 worker 仍必须本地复核。
11. YAML 配置保留给人阅读，运行时先使用 JSON 配置，避免未安装 PyYAML 时无法启动。
12. 模型调用通过 provider adapter 隔离，当前 NullProvider 会明确报 `provider.not_configured`。
13. 当前执行器只允许只读命令进入 dry-run 校验，不执行真实 shell。
14. 删除、未知命令、网络下载、系统命令默认被拒绝。
15. profile 必须能编译成可达 graph，未知节点、重复节点、孤立节点会报 `validation.failed`。
16. approval 绑定的 plan_hash 包含 graph plan，profile 图变化会导致旧批准失效。
17. GraphRunner 与 server/executor/provider 隔离，只负责节点 trace 和错误捕获。
18. 节点失败不会被吞掉，会形成 `graph_node_failed`/`run_failed` 事件。
19. 每个 agent 节点通过 handler 注册表接入，GraphRunner 不知道具体业务实现。
20. handler 的职责是生成节点级输出，不允许直接越过 PolicyEngine 或 Executor。
21. local_qwen 只作为应急对话和低风险推理模型，不能替代 Codex 或审批高风险操作。
```

### 已遇到的问题

#### Python 依赖尚未安装

检查命令：

```powershell
python -c "import pydantic, fastapi, httpx, pytest; print('ok')"
```

结果：

```text
ModuleNotFoundError: No module named 'pydantic'
```

处理方式：

```text
暂时先写标准库可验证的核心模块。
FastAPI/httpx/Pydantic 相关入口已写好，但需要安装依赖后才能运行 server/worker 的完整网络流程。
```

后续安装方式：

```powershell
cd E:\agents
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .[dev]
```

如果 pip 因网络失败：

```text
1. 确认网络代理或校园网是否可访问 PyPI。
2. 可换国内镜像源。
3. 依赖安装失败时不要继续启动 server，先解决环境。
```

#### unittest 找不到 safeagent 包

检查命令：

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

结果：

```text
ModuleNotFoundError: No module named 'safeagent'
```

原因：

```text
当前项目使用 src/ 布局，但还没有执行 pip install -e .。
未安装前，Python 默认不会自动把 E:\agents\src 加入 import 路径。
```

临时验证方式：

```powershell
$env:PYTHONPATH="E:\agents\src"
python -m unittest discover -s tests -p "test_*.py"
```

正式处理方式：

```powershell
cd E:\agents
.\.venv\Scripts\python.exe -m pip install -e .[dev]
```

实际补充处理：

```text
当前测试文件是 pytest 风格函数。为了不依赖 pytest，新增了 scripts/run_stdlib_tests.py。
```

验证命令：

```powershell
python .\scripts\run_stdlib_tests.py
```

结果：

```text
passed=39 failed=0
```

语法检查：

```powershell
python -m compileall src scripts tests
```

结果：

```text
通过。
```

清理：

```text
compileall 和测试会生成 __pycache__，验证后已清理。
```

新增覆盖：

```text
1. plan_hash 稳定性。
2. approval 决策、过期时间、plan_hash 错配。
3. server store 最新 approval 读取。
4. server/shared 模块边界隔离。
5. agent/profile registry 加载与缺失 agent 报错。
6. model router 低风险/高风险分流。
7. provider 未配置时的清晰错误。
8. dry-run executor allowlist。
9. 删除命令和未知命令拒绝。
10. orchestrator 输出 command_proposed / command_validated 事件。
11. profile graph plan 编译。
12. graph edge 未知节点和不可达节点报错。
13. graph runner 成功 trace。
14. graph runner 节点失败转换为 ErrorEnvelope。
15. local_qwen emergency route。
16. local_qwen 高风险不宣称可审批。
17. local provider 不可达时返回 retriable upstream error。
```

#### SQLite 文件被占用

新增 `TaskStore` 测试后，第一次运行出现：

```text
[WinError 32] 另一个程序正在使用此文件，进程无法访问。: '<temp>\\server.sqlite3'
```

原因：

```text
sqlite3.Connection 作为 context manager 时会自动 commit/rollback，但不会自动 close。
Windows 删除临时目录时发现 sqlite 文件仍被连接占用。
```

修复：

```text
在 TaskStore 中新增 _connection() context manager，统一 commit/rollback/close。
所有数据库操作改用 _connection()。
```

#### dataclass schema 不自动转换枚举

新增 `RunEvent` 测试时出现：

```text
'str' object has no attribute 'value'
```

原因：

```text
RunEvent 当前是标准库 dataclass，不是 Pydantic model。
测试里把 event_type 写成了字符串，to_dict() 期望它是 EventType 枚举。
```

处理：

```text
测试改为显式传入 EventType.RUN_COMPLETED。
这符合当前设计：内部模块使用强类型枚举，API 边界再负责字符串解析和校验。
```

### 下一步

```text
1. 安装依赖后验证 FastAPI server。
2. 添加 API 层测试或集成 smoke test。
3. 实现真实 Executor 前的命令白名单和确认机制。
4. 安装依赖后验证 FastAPI API 层。
5. 实现真实 DeepSeek/Codex provider adapter。
6. 将 GraphPlan 接入 LangGraph StateGraph。
7. 为 GraphRunner 增加真实节点 handler 注册机制。
```

## 2026-05-30 本地 Qwen 低内存部署口径修正

用户补充：

```text
1. 本地模型尚未部署。
2. 希望低内存部署。
3. 用户明确要求直接上 35B。
```

调整：

```text
1. docs/LOCAL_QWEN.md 从“Qwen 35B 已部署假设”改为“直接 35B/32B 级低内存部署路线”。
2. 明确低内存优先参数：GGUF + Q4_K_M + 小上下文 + 单并发。
3. 默认模型名示例改为 qwen-35b-local。
4. 补充 llama-server OpenAI-compatible API 方向。
5. 小模型只保留为排障 fallback，不作为主路线。
6. docs/USAGE.md 增加 35B/32B 级部署摘要。
7. docs/TROUBLESHOOTING.md 增加“尚未部署”和“内存不足/很慢”的处理方法。
```

安全边界保持不变：

```text
1. local_qwen 只做应急对话、摘要和低风险解释。
2. local_qwen 不能替代 Codex。
3. local_qwen 不能批准高风险操作。
4. local_qwen 输出仍然必须经过 PolicyEngine。
```

验证：

```text
1. 文档关键字核对通过：qwen-35b-local / Q4_K_M / llama-server / 35B/32B 均已对齐。
2. python .\scripts\run_stdlib_tests.py 通过：passed=39 failed=0。
3. 测试生成的 __pycache__ 已清理。
```

## 2026-05-30 Provider 配置和框架路线补强

本轮目标：

```text
1. 保持长期框架路线仍为 LangGraph。
2. 在当前 MVP 中继续使用标准库 GraphRunner 稳定安全骨架。
3. 为 DeepSeek / Codex / local_qwen provider 做统一配置入口。
4. 防止 API Key 进入事件日志和云端摘要。
```

代码调整：

```text
1. .env.example 增加 DeepSeek / Codex / timeout 环境变量。
2. WorkerSettings 增加 DeepSeek / Codex / timeout 配置字段。
3. providers.py 将 OpenAI-compatible 适配器泛化，不只服务 local_qwen。
4. build_provider_registry() 只注册环境变量完整的远程 provider。
5. Provider public_status() 只暴露 has_api_key，不暴露真实 key。
6. LocalWorker 从本地环境变量构建 provider registry。
7. LocalOrchestrator 的 model_router 事件增加 provider_status。
8. docs/USAGE.md 增加“框架路线”说明：MVP GraphRunner 后续映射 LangGraph StateGraph。
9. docs/TROUBLESHOOTING.md 补充 provider 未配置和响应格式不兼容处理方式。
```

安全边界：

```text
1. provider 只负责模型调用，不获得执行权限。
2. provider 配置来自本地环境变量，不来自云端任务。
3. 云端事件只能看到 provider 是否配置，不能看到 API Key。
4. Codex provider 即使配置，也只是审查模型，不直接批准执行。
```

验证：

```text
1. python .\scripts\run_stdlib_tests.py 通过：passed=42 failed=0。
2. python -m compileall src scripts tests 通过。
3. 文档关键字核对通过：qwen-35b-local / SAFEAGENT_DEEPSEEK / SAFEAGENT_CODEX / LangGraph / GraphRunner / has_api_key。
4. 验证生成的 __pycache__ 已清理。
```

## 2026-05-30 Approval 闭环补强

本轮目标：

```text
1. 远程 approval 不能直接变成执行权限。
2. approved 后任务必须重新入队，由本地 worker 重新拉取。
3. 本地 worker 必须重新计算 plan_hash 并校验 approval。
4. approval 过期、hash 不一致、decision 非 approved 时必须拒绝。
```

代码调整：

```text
1. server record_approval() 在 decision=approved 时将任务状态设回 pending。
2. server 增加 GET /api/tasks/{task_id}/approval/latest。
3. TaskStore 增加 latest_approval_for_task()。
4. ControlPlaneClient 增加 fetch_latest_approval()。
5. LocalWorker 处理任务前读取最新 approval。
6. LocalOrchestrator 对 medium 风险任务调用 check_approval()。
7. approval 有效时只完成 dry-run；approval 无效时返回 rejected。
```

新增测试：

```text
1. latest_approval_for_task() 返回最新 approval。
2. medium 风险任务无 approval 时 waiting_approval。
3. plan_hash 不匹配时 rejected。
4. 当前 plan_hash + 未过期 approval 时 completed dry-run。
```

安全边界：

```text
1. approval 只绑定 plan_hash，不绑定模型输出的自由文本。
2. approval 不能绕过 PolicyEngine。
3. approval 不能让高风险 blocked 任务自动执行。
4. 当前 Executor 仍然是 dry-run。
```

验证：

```text
1. python .\scripts\run_stdlib_tests.py 通过：passed=45 failed=0。
2. python -m compileall src scripts tests 通过。
3. 文档关键字核对通过：plan_hash / 重新入队 / rejected / waiting_approval / dry-run。
4. 验证生成的 __pycache__ 已清理。
```

## 2026-05-30 命令级 gate 补强

本轮目标：

```text
1. 每条命令提案都必须有稳定 command_hash。
2. command_hash 必须进入 plan_hash。
3. approval 事件必须能追溯到具体命令。
4. 默认执行模式继续保持 dry_run。
5. 误设 live 执行模式时必须拒绝，而不是执行。
```

代码调整：

```text
1. CommandProposal.to_dict() 增加 command_hash。
2. executor.py 增加 command_fingerprint()。
3. CommandValidation 增加 command_hash 和 execution_mode。
4. ExecutionResult 增加 execution_mode。
5. CommandValidator.validate() 接收 execution_mode。
6. DryRunExecutor 在 execution_mode != dry_run 时拒绝。
7. WorkerSettings 增加 SAFEAGENT_EXECUTION_MODE，默认 dry_run。
8. LocalOrchestrator 将 command 和 command_hash 纳入 plan_hash。
9. LocalOrchestrator 在关键事件 details 中记录 command_hash。
```

新增测试：

```text
1. readonly 命令验证结果包含 command_hash。
2. 命令参数变化会改变 command_hash。
3. live execution mode 在 MVP 中被拒绝。
4. topology_router 和 policy_engine 事件中的 command_hash 一致。
5. approval_requested / approval_recorded 事件包含 command_hash。
```

安全边界：

```text
1. 当前不会执行真实 shell。
2. command_hash 不代替 approval，只作为可审计绑定材料。
3. execution_mode 变更会进入 plan_hash，使旧 approval 失效。
4. 真实执行仍需后续补命令级 approval、超时、脱敏、审计和回滚。
```

验证：

```text
1. python .\scripts\run_stdlib_tests.py 通过：passed=47 failed=0。
2. python -m compileall src scripts tests 通过。
3. 文档关键字核对通过：SAFEAGENT_EXECUTION_MODE / command_hash / command_fingerprint / live execution / dry_run。
4. 验证生成的 __pycache__ 已清理。
```

## 2026-05-30 执行输出审计层

本轮目标：

```text
1. 即使当前仍是 dry-run，也先固定 ExecutionResult 的输出审计结构。
2. stdout / stderr 必须先脱敏再截断。
3. 执行结果必须记录截断状态和原始长度。
4. worker 配置中预留执行超时和输出长度限制。
```

代码调整：

```text
1. executor.py 增加 ExecutionOutputAudit。
2. ExecutionResult 增加 timeout_seconds 和 output_audit。
3. executor.py 增加 audit_execution_output()。
4. executor.py 增加 truncate_text()，负数限制返回 validation.failed。
5. DryRunExecutor 对 dry-run stderr 也走统一输出审计。
6. WorkerSettings 增加 execution_timeout_seconds / stdout_limit_chars / stderr_limit_chars。
7. .env.example 增加 SAFEAGENT_EXECUTION_TIMEOUT_SECONDS / SAFEAGENT_STDOUT_LIMIT_CHARS / SAFEAGENT_STDERR_LIMIT_CHARS。
8. LocalOrchestrator / LocalWorker 将这些配置传给 executor。
```

新增测试：

```text
1. dry-run result 包含 timeout_seconds 和 output_audit。
2. audit_execution_output() 会脱敏并截断。
3. truncate_text() 拒绝负数限制。
```

测试修正：

```text
第一次截断测试使用 "x" * 40 作为 stderr。
该字符串会被现有敏感值规则当成长 token 脱敏成 [REDACTED]，因此没有触发截断。
测试输入改为 "error line " * 10，用于验证非敏感大输出截断。
```

安全边界：

```text
1. 当前仍不执行真实 shell。
2. 输出审计先于未来云端事件上传。
3. 大输出不会直接无限制进入日志结构。
4. 敏感值被 redact_text() 处理后才进入 ExecutionResult。
```

验证：

```text
1. python .\scripts\run_stdlib_tests.py 通过：passed=49 failed=0。
2. python -m compileall src scripts tests 通过。
3. 文档关键字核对通过：output_audit / STDOUT_LIMIT / STDERR_LIMIT / EXECUTION_TIMEOUT / TRUNCATED / REDACTED / timeout_seconds。
4. 验证生成的 __pycache__ 已清理。
```

## 2026-05-30 最小 live_readonly 执行门

本轮目标：

```text
1. 保持 dry_run 默认。
2. 引入极小真实只读执行模式 live_readonly。
3. live_readonly 必须由独立开关启用。
4. live_readonly 仍然必须先经过 approval。
5. COMMAND_VALIDATED 只能校验，不能提前执行。
```

代码调整：

```text
1. executor.py 增加 LIVE_READONLY_COMMANDS，只包含 Get-ChildItem / Get-Item / Test-Path。
2. executor.py 增加 first_unsafe_live_arg()，拒绝高风险参数字符。
3. executor.py 增加 build_live_readonly_process_args()，使用 subprocess list + shell=False。
4. CommandValidator 增加 allow_live_readonly。
5. execution_mode 只支持 dry_run / live_readonly。
6. live_readonly 需要 SAFEAGENT_ENABLE_LIVE_READONLY=true。
7. WorkerSettings 增加 enable_live_readonly。
8. LocalOrchestrator 将 live_readonly_enabled / execution_requires_approval 纳入 plan_hash。
9. LocalOrchestrator 修复执行顺序：先 validate，approval 通过后才 execute。
```

新增测试：

```text
1. live_readonly 未开启时被拒绝。
2. live_readonly 开启后只允许极小只读子集。
3. unsafe 参数被拒绝。
4. subprocess 参数使用列表，不使用 shell 字符串。
5. orchestrator 在 live_readonly 下先 waiting_approval，不提前执行。
6. live_readonly 未启用时 orchestrator blocked。
```

安全边界：

```text
1. 默认仍为 dry_run。
2. live_readonly 不是通用 live 执行。
3. low risk 任务在 live_readonly 下也需要 approval。
4. execution_mode 和 live_readonly_enabled 会进入 plan_hash。
5. 旧 approval 不能跨执行模式复用。
```

验证：

```text
1. python .\scripts\run_stdlib_tests.py 通过：passed=55 failed=0。
2. python -m compileall src scripts tests 通过。
3. 文档关键字核对通过：live_readonly / ENABLE_LIVE_READONLY / COMMAND_VALIDATED / execution_requires_approval / shell=False / Test-Path。
4. 验证生成的 __pycache__ 已清理。
```

## 2026-05-30 Agent/Profile 安全契约

本轮目标：

```text
1. 防止配置文件让非 executor agent 获得执行或写入权限。
2. 防止联网权限扩散到非 search_agent。
3. 防止 executor 被绕过 reviewer / approval 直接访问。
4. 防止新增 profile 时破坏安全拓扑。
```

代码调整：

```text
1. AgentRegistry 初始化时执行 _validate_agent_security_contracts()。
2. ProfileRegistry 初始化时执行 _validate_profile_security_contract()。
3. 只有 executor 可以 can_execute=true 或 can_write=true。
4. local_executor 工具保留给 executor。
5. 默认只有 search_agent 可以 network.allowed=true。
6. search_agent 必须 search_only 且 can_download=false。
7. codex_review model_policy 保留给 codex_reviewer。
8. human_approval model_policy 必须是 none。
9. 含 executor 的 profile 必须包含 rule_reviewer / human_approval。
10. executor 必须有 human_approval -> executor 且 condition=approved 的边。
11. executor 只能从 rule_reviewer 或 human_approval 到达。
12. 含联网 agent 的 profile 必须 network_mode=search_allowed。
```

新增测试：

```text
1. 非 executor 拥有 can_execute 会失败。
2. search_agent 开启 can_download 会失败。
3. 含 executor 但缺少 approved human_approval 边会失败。
4. api_only profile 包含 search_agent 会失败。
```

安全边界：

```text
1. Agent 扩展仍然允许，但权限默认不能膨胀。
2. 配置错误会在 worker 启动阶段失败。
3. 新增高权限能力必须同步新增策略和测试。
```

验证：

```text
1. python .\scripts\run_stdlib_tests.py 通过：passed=59 failed=0。
2. python -m compileall src scripts tests 通过。
3. 文档关键字核对通过：Agent 安全契约 / Profile 安全契约 / Only executor / search_only / human_approval / network-enabled / can_download / local_executor。
4. 验证生成的 __pycache__ 已清理。
```

## 2026-05-30 配置同步检查

本轮目标：

```text
1. 防止 configs/*.yaml 和 configs/*.json 漂移。
2. 让配置同步检查在未安装 PyYAML 的环境里也能运行。
3. 将 registry 安全契约检查纳入脚本入口。
```

代码调整：

```text
1. 新增 src/safeagent/local_worker/config_sync.py。
2. 新增 canonical_config()，用于 YAML/JSON 语义比较。
3. 新增 load_json_config()，提供清晰 JSON 错误。
4. 新增 load_yaml_config()，优先使用 PyYAML。
5. PyYAML 不存在时，使用 parse_yaml_subset() 解析当前配置文件使用的 YAML 子集。
6. 新增 scripts/check_config_sync.py。
7. check_config_sync.py 同时检查 YAML/JSON 同步和 registry 安全契约。
```

新增测试：

```text
1. canonical_config() 对 dict key 排序但不改变 list 顺序。
2. invalid JSON 返回 validation.failed。
3. missing YAML 返回 validation.failed。
4. fallback YAML parser 支持当前配置子集。
5. 当前 YAML 配置可被 fallback parser 解析。
6. 当前 JSON 配置有效。
```

验证：

```text
1. python .\scripts\run_stdlib_tests.py 通过：passed=65 failed=0。
2. python .\scripts\check_config_sync.py 通过：OK config YAML/JSON sync and registry security contracts。
3. python -m compileall src scripts tests 通过。
4. 文档关键字核对通过：check_config_sync / YAML/JSON / parse_yaml_subset / PyYAML / registry security contracts / 配置同步。
5. 验证生成的 __pycache__ 已清理。
```

## 2026-05-30 本地闭环 Smoke Test

本轮目标：

```text
1. 提供不依赖 FastAPI / httpx / PyYAML 的本地端到端 smoke test。
2. 验证 TaskStore + LocalOrchestrator + approval + policy 可以串起来。
3. 在后续改动 approval、policy、registry、orchestrator 时提供快速回归入口。
```

代码调整：

```text
1. 新增 scripts/smoke_local_flow.py。
2. run_smoke() 使用临时 SQLite TaskStore。
3. 创建中风险 copy-item 任务并验证 waiting_approval。
4. 记录 approval 后重新入队，再次 claim 后验证 completed dry-run。
5. 创建高风险 diskpart 任务并验证 blocked。
6. 新增 tests/test_smoke_local_flow.py。
```

验证：

```text
1. python .\scripts\smoke_local_flow.py 通过：OK local smoke flow。
2. python .\scripts\run_stdlib_tests.py 通过：passed=66 failed=0。
3. python .\scripts\check_config_sync.py 通过：OK config YAML/JSON sync and registry security contracts。
4. python -m compileall src scripts tests 通过。
5. 文档关键字核对通过：smoke_local_flow / OK local smoke flow / medium_status / high_status / 本地闭环 Smoke Test / FAIL smoke_local_flow。
6. 验证生成的 __pycache__ 已清理。
```

## 2026-05-30 Doctor 聚合自检入口

本轮目标：

```text
1. 提供一个日常自检入口，避免手动记多个命令。
2. quick 模式覆盖配置同步、smoke、compileall。
3. 完整模式额外运行标准库测试。
4. 输出中按 check 名称定位失败来源。
```

代码调整：

```text
1. 新增 src/safeagent/local_worker/doctor.py。
2. 新增 DoctorCheckResult。
3. 新增 doctor_exit_code()。
4. 新增 format_doctor_report()。
5. 新增 scripts/doctor.py。
6. doctor.py --quick 跳过完整测试套件。
7. doctor.py 默认运行 stdlib tests。
8. 新增 tests/test_doctor.py。
```

验证：

```text
1. python .\scripts\doctor.py --quick 通过：OK doctor checks。
2. python .\scripts\run_stdlib_tests.py 通过：passed=68 failed=0。
3. python .\scripts\doctor.py 通过：OK doctor checks。
4. python -m compileall src scripts tests 通过。
5. 文档关键字核对通过：doctor.py / OK doctor checks / FAIL doctor checks / config_sync / local_smoke / stdlib_tests / Doctor。
6. 验证生成的 __pycache__ 已清理。
```

安全边界：

```text
1. smoke test 不启动 server，不访问网络。
2. smoke test 不执行真实 shell。
3. smoke test 验证高风险任务仍然 blocked。
4. smoke test 验证 approval 不稳定时会破坏 completed 路径。
```

## 2026-05-30 Node Handler 模型调用隔离

本轮目标：
```text
1. 让 planner / producer / reviewer / summarizer 节点可以通过统一边界调用模型。
2. provider 未配置、不可达或返回错误时，不让整个 graph runner 失败。
3. 确保模型错误输出进入结构化节点结果，并做脱敏。
4. 保持 executor / human_approval 不通过模型间接获得执行权。
```

代码调整：
```text
1. 在 src/safeagent/local_worker/node_handlers.py 新增 ModelInvoker 协议。
2. 新增 ProviderModelInvoker，将 ProviderRegistry 包装成节点可用的安全调用接口。
3. provider.not_configured / upstream / validation 等 SafeAgentError 会被捕获为 node output。
4. 未知异常会转成 model.invocation_failed，不抛出到 GraphRunner。
5. 模型调用结果包含 model_status / model / purpose / usage。
6. 模型调用成功 content 和错误都会通过 redact_payload() 脱敏。
7. LocalOrchestrator 构造 GraphRunner 时注入当前 ProviderRegistry。
8. human_approval 和 executor 仍保持无模型、无真实副作用。
```

新增测试：
```text
1. provider 可用时，planner 节点记录模型输出和 token/cost 元数据。
2. provider 未配置时，节点输出 model_status=unavailable，graph 仍 completed。
3. provider 报错包含 API key 时，graph 仍 completed，序列化结果不包含原始 key。
4. provider 成功输出中包含 API key 时，节点 content 会脱敏。
```

安全边界：
```text
1. 节点模型调用只产生建议或摘要，不执行 shell、不联网、不写文件。
2. 模型 provider 故障不会跨模块拖垮 policy / approval / executor。
3. executor 的真实执行仍只发生在 orchestrator 的 policy 和 approval gate 之后。
4. human_approval 不调用模型，避免模型伪造人工确认。
```

验证：
```text
1. python .\scripts\run_stdlib_tests.py 通过：passed=72 failed=0。
2. python .\scripts\doctor.py 通过：OK doctor checks。
3. doctor 覆盖 config_sync / local_smoke / compileall / stdlib_tests。
4. compileall 生成的 __pycache__ 已清理。
```

## 2026-05-30 GraphRunner 条件分支隔离

本轮目标：
```text
1. 让 GraphRunner 不再无条件按 nodes 列表运行所有 agent。
2. 按 profile edges 和 condition 保守选择本次任务实际路径。
3. 防止 human_approval / codex_reviewer / executor 等节点在条件不满足时被误跑。
4. 为后续 LangGraph conditional edges 迁移稳定语义。
```

代码调整：
```text
1. GraphRunner 从 graph.entry 开始遍历。
2. 新增 edges_by_source，用 profile edges 决定后继节点。
3. 支持 low / medium / high / medium_or_higher / approved / review_passed。
4. approved 只读取 GraphState.payload.approval_valid=true。
5. review_passed 只接受上游 node output.review_status=passed。
6. 未知 condition 返回 validation.failed。
7. LocalOrchestrator 在 plan_hash 计算后预校验 approval，并把有效结果注入 graph payload。
8. approval_valid 不进入 plan_hash，避免改变 approval 绑定语义。
```

新增测试：
```text
1. low risk 跳过 human_approval 分支。
2. medium risk 无 approval 时停在 human_approval。
3. medium risk 有有效 approval 时进入 executor / summarizer。
4. high risk code_change 不把 placeholder review 当作 review_passed。
5. 未知 condition 会产生结构化 graph failure。
6. orchestrator 有效 approval 时，graph trace 能看到 executor 分支。
```

验证：
```text
1. python .\scripts\run_stdlib_tests.py 通过：passed=77 failed=0。
2. python .\scripts\doctor.py 通过：OK doctor checks。
3. doctor 覆盖 config_sync / local_smoke / compileall / stdlib_tests。
```

## 2026-05-30 GraphRunner Edge Decision Trace

本轮目标：
```text
1. 让 graph trace 说明每条条件边为什么被选择或跳过。
2. 方便排查“某个 agent 为什么没有运行”。
3. 保留 node_results 兼容性，不破坏现有事件结构。
```

代码调整：
```text
1. 新增 EdgeDecision dataclass。
2. GraphRunResult 新增 edge_decisions 字段。
3. EdgeDecision 包含 from / to / condition / selected / reason。
4. 未知 condition 失败时也会记录一条 selected=false 的 edge decision。
5. condition 判断现在返回 matches + reason。
```

新增测试：
```text
1. low risk 下 human_approval 分支 selected=false, reason=risk_level=low。
2. medium risk 无 approval 下 executor 分支 selected=false, reason=approval_valid=False。
3. 有 approval 下 executor 分支 selected=true, reason=approval_valid=True。
4. review_passed 未满足时记录 review_status=missing 或 placeholder。
5. 未知 condition 失败时记录 edge_decision。
```

验证：
```text
1. python .\scripts\run_stdlib_tests.py 通过：passed=77 failed=0。
2. python .\scripts\doctor.py 通过：OK doctor checks。
3. doctor 覆盖 config_sync / local_smoke / compileall / stdlib_tests。
```

## 2026-05-30 Run Diagnostics 摘要

本轮目标：
```text
1. 让 /api/runs/{run_id} 直接返回稳定诊断摘要。
2. 避免用户必须深入 events.details 才能判断失败、阻塞、等待审批原因。
3. 诊断生成逻辑放在 shared 层，server 不依赖 local_worker。
4. 诊断只从已脱敏 events/approvals 推导。
```

代码调整：
```text
1. 新增 src/safeagent/shared/diagnostics.py。
2. 新增 build_run_diagnostics(events, approvals)。
3. TaskStore.get_run() 返回 diagnostics 字段。
4. diagnostics 包含 status / event_count / approval_count / agents / risk_level / network_modes。
5. diagnostics 包含 event_type_counts / error_count / errors / blocking_reasons / edge_decisions。
6. diagnostics 输出再次经过 redact_payload()。
```

新增测试：
```text
1. completed run 会生成 completed 摘要。
2. execution_skipped 会进入 blocking_reasons，并脱敏 reason。
3. graph node error 会进入 errors。
4. edge_decisions 会统计 selected / skipped / failed。
5. TaskStore.get_run() 会返回 diagnostics。
```

验证：
```text
1. python .\scripts\run_stdlib_tests.py 通过：passed=80 failed=0。
2. python .\scripts\doctor.py 通过：OK doctor checks。
3. doctor 覆盖 config_sync / local_smoke / compileall / stdlib_tests。
```

## 2026-05-30 模块边界 AST 检查

本轮目标：
```text
1. 防止 server / shared / local_worker 互相越层 import。
2. 用 AST 检查替代字符串搜索，减少误报漏报。
3. 将模块边界检查接入 doctor。
4. 让边界失败输出具体文件、行号和违规 import。
```

代码调整：
```text
1. 新增 src/safeagent/shared/module_boundaries.py。
2. 新增 BoundaryViolation。
3. 新增 check_module_boundaries(root)。
4. 新增 format_boundary_report()。
5. 新增 scripts/check_module_boundaries.py。
6. scripts/doctor.py 新增 module_boundaries 检查。
```

当前硬边界：
```text
1. safeagent.shared 不能 import safeagent.server。
2. safeagent.shared 不能 import safeagent.local_worker。
3. safeagent.server 不能 import safeagent.local_worker。
4. safeagent.local_worker 不能 import safeagent.server。
```

新增测试：
```text
1. 当前项目边界无违规。
2. shared -> local_worker 会失败。
3. worker -> server 会失败。
4. server -> worker 会失败。
5. 失败报告包含可定位信息。
```

验证：
```text
1. python .\scripts\run_stdlib_tests.py 通过：passed=83 failed=0。
2. python .\scripts\doctor.py 通过：OK doctor checks。
3. doctor 覆盖 config_sync / module_boundaries / local_smoke / compileall / stdlib_tests。
```

## 2026-05-30 Edge Condition 配置前置校验

本轮目标：
```text
1. 将 edge condition 的合法词表集中到 shared 层。
2. Registry 加载 profile 时前置拒绝未知 condition。
3. GraphRunner 复用同一套 condition 语义，避免配置层和运行层漂移。
```

代码调整：
```text
1. 新增 src/safeagent/shared/graph_conditions.py。
2. 新增 ALLOWED_EDGE_CONDITIONS。
3. 新增 is_allowed_edge_condition()。
4. 新增 risk_condition_matches()。
5. ProfileRegistry 校验 unsupported edge condition。
6. GraphRunner 使用 graph_conditions 常量和 risk_condition_matches()。
```

当前允许 condition：
```text
low
medium
high
medium_or_higher
approved
review_passed
```

新增测试：
```text
1. graph condition 白名单固定且显式。
2. risk condition 匹配语义正确。
3. profile 中未知 condition 会在 registry 阶段失败。
```

验证：
```text
1. python .\scripts\run_stdlib_tests.py 通过：passed=86 failed=0。
2. python .\scripts\doctor.py 通过：OK doctor checks。
3. doctor 覆盖 config_sync / module_boundaries / local_smoke / compileall / stdlib_tests。
```

## 2026-05-31 远程权限 API 前置校验

本轮目标：
```text
1. 让远程 submit_task / approval_only / view_only 权限在 API 层生效。
2. 防止 view_only 或 approval_only 越权提交新任务。
3. 防止 view_only 越权批准任务。
4. 保持本地 MVP 未传权限头时的兼容行为。
```

代码调整：
```text
1. 新增 src/safeagent/shared/remote_permissions.py。
2. 新增 parse_remote_permission()。
3. 新增 require_submit_task_permission()。
4. 新增 require_approval_permission()。
5. 新增 validate_task_remote_permission()。
6. 新增 RemotePermissionError，返回 auth.failed 且带权限 details。
7. POST /api/tasks 校验 X-SafeAgent-Remote-Permission=submit_task。
8. POST /api/tasks/{task_id}/approval 允许 approval_only 或 submit_task。
```

权限规则：
```text
view_only：只能查看。
approval_only：可以 approval，不能 submit task。
submit_task：可以 submit task，也可以 approval。
```

新增测试：
```text
1. 未传权限默认 submit_task，兼容本地 MVP。
2. 未知权限返回 validation.failed。
3. view_only / approval_only 不能 submit task。
4. view_only 不能 approval。
5. 新任务 body.remote_permission 必须是 submit_task。
```

验证：
```text
1. python .\scripts\run_stdlib_tests.py 通过：passed=91 failed=0。
2. python .\scripts\doctor.py 通过：OK doctor checks。
3. doctor 覆盖 config_sync / module_boundaries / local_smoke / compileall / stdlib_tests。
```

## 2026-05-31 Task Status 生命周期保护

本轮目标：
```text
1. 防止云端或调用方把 task 任意改成终态。
2. 防止 completed / failed / blocked / rejected 等终态回滚。
3. 未知 task_id 更新状态时返回清晰 validation.failed。
4. 保持 worker claim / waiting_approval / approval 重新入队 / terminal 流程可用。
```

代码调整：
```text
1. 新增 src/safeagent/shared/task_lifecycle.py。
2. 新增 ALLOWED_TASK_STATUS_TRANSITIONS。
3. 新增 is_valid_task_status_transition()。
4. TaskStore.update_task_status() 先读取当前状态。
5. 不存在 task_id 时返回 Cannot update status for unknown task。
6. 不合法状态跳转时返回 Invalid task status transition。
```

允许的主要路径：
```text
pending -> claimed
claimed -> running / waiting_approval / completed / failed / blocked / rejected
running -> waiting_approval / completed / failed / blocked / rejected
waiting_approval -> pending / rejected
terminal -> 不允许回滚
```

新增测试：
```text
1. worker + approval 正常状态路径可用。
2. terminal 状态不能回滚。
3. pending 不能直接 completed。
4. unknown task status update 返回 validation.failed。
5. TaskStore 拒绝非法状态跳转。
```

验证：
```text
1. python .\scripts\run_stdlib_tests.py 通过：passed=97 failed=0。
2. python .\scripts\doctor.py 通过：OK doctor checks。
3. doctor 覆盖 config_sync / module_boundaries / local_smoke / compileall / stdlib_tests。
```

## 2026-05-31 路线和优先级固定

本轮目标：
```text
1. 将当前项目进度与最初设想重新对齐。
2. 固定后续优先级，避免继续被局部小补丁带偏。
3. 明确安全是 P0，LangGraph 是 P1。
4. 明确当前 GraphRunner 只是迁移前的安全语义验证层。
```

文档调整：
```text
1. 新增 docs/ROADMAP_STATUS.md。
2. README.md 增加 Priority Order。
3. README.md 指向 docs/ROADMAP_STATUS.md。
4. docs/ROADMAP_STATUS.md 明确安全 > 可控性 > 可追溯性 > LangGraph 迁移速度。
5. docs/ROADMAP_STATUS.md 增加 LangGraph 迁移验收条件。
```

固定优先级：
```text
P0 Safety boundaries and clear error handling
P1 LangGraph core orchestration
P2 End-to-end MVP task loop
P3 Model providers
P4 Controlled local computer operations
P5 Remote control UI and cloud deployment
P6 Knowledge base, memory, and long-term extensions
```

不可退让约束：
```text
1. LangGraph 只负责编排，不取代安全层。
2. PolicyEngine 仍是风险判断核心。
3. Executor 仍是唯一执行边界。
4. approval / plan_hash / audit log / redaction 不能被迁移削弱。
```
