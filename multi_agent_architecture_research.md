# Multi-Agent Architecture Research Notes

## 目标

为本地电脑多智能体系统设计一个可变、可审计、可控、性价比高的协作架构。系统允许受控操作电脑，但默认将自身项目文件、日志、缓存、状态、生成物和备份集中放在 `E:\agents`。

核心问题：

1. 多智能体之间的关系不能固定死，应能按任务调整。
2. DeepSeek 和 Codex 的 token 应按风险、质量需求和成本动态分流。
3. 系统必须有清晰日志、错误预警、审查记录和可回放能力。
4. 执行层不能让模型直接获得无限制电脑权限。

## 论文与框架结论

### 1. 固定角色协作适合 MVP，但不适合长期复杂任务

AutoGen 证明了多 agent 对话框架适合把 LLM、人类输入和工具组合成可编排应用。它的价值在于 agent 可定制、可对话、可组合，但如果直接照搬“多个 agent 自由聊天”，容易带来上下文膨胀、责任不清和日志难追踪。

MetaGPT、ChatDev 这类软件开发型多智能体系统说明固定角色流程适合工程任务，例如产品经理、架构师、工程师、测试员。但这类流程更像预设流水线，灵活性不够。

结论：MVP 可以使用固定角色，但长期架构应抽象成可配置图，而不是固定队列。

### 2. 可变关系应采用动态图 / 可优化图

DyLAN 提出动态 LLM agent 网络，核心是先优化团队，再执行任务。GPTSwarm 将语言 agent 系统表示为可优化图，重点是优化节点提示词和边连接关系。DynaSwarm 进一步强调按任务动态选择多智能体图结构。

结论：本项目应把 agent 关系建模为图：

```text
Agent = 节点
消息 / 任务委派 / 审查 / 交接 = 边
Orchestrator / Router = 决定当前图结构的控制器
```

不要把 agent 关系写死为：

```text
Planner → Coder → Reviewer → Executor
```

而应支持多个拓扑：

```text
线性模式：Planner → Worker → Reviewer → Executor
星型模式：Orchestrator → 多个 Worker → Orchestrator
辩论模式：多个 Reviewer 并行审查 → Judge 合并
级联模式：Cheap Model → Strong Model only if needed
专家模式：Router → File / Code / Shell / Research 专家
审查模式：Worker → Rule Reviewer → Codex Reviewer → Human
```

### 3. 不是 agent 越多越好

Mixture-of-Agents 和 LLM-Blender 说明多模型/多 agent 可以提升质量，但代价是延迟和 token 成本显著上升。More Agents / voting 类方法在难题上可能有效，但不适合日常电脑自动化，因为每一步都多 agent 投票会浪费 token。

结论：agent 数量应由任务复杂度和风险等级决定。默认少 agent，高风险或高不确定性再加 reviewer、judge 或 parallel workers。

### 4. 成本优化应使用模型路由和级联

FrugalGPT 提出 prompt adaptation、LLM approximation、LLM cascade 三类降本策略。RouteLLM 通过偏好数据训练路由器，在强弱模型之间动态选择，以平衡成本和质量。

结论：DeepSeek / Codex 不应写死为“DeepSeek 干活、Codex 审查”这么简单。应实现 Model Router：

```text
低风险 / 普通文本 / 日志摘要 → DeepSeek
普通代码草案 / 命令草案 → DeepSeek
规则可判定风险 → 本地规则
中风险命令 → DeepSeek review + 用户确认
高风险命令 / 复杂 diff / 系统操作 → Codex review + 用户确认
DeepSeek 低置信度或多次失败 → 升级到 Codex
Codex 审查后仍不确定 → 只给建议，不执行
```

## 推荐总体架构

```text
User
 ↓
Task Intake
 ↓
Orchestrator
 ├── Task Classifier
 ├── Topology Router
 ├── Model Router
 ├── Risk Router
 ├── Budget Manager
 └── State Manager
 ↓
Dynamic Agent Graph
 ├── Planner Agent
 ├── Research Agent
 ├── File Agent
 ├── Code Agent
 ├── Shell Agent
 ├── Reviewer Agent
 ├── Codex Reviewer
 ├── Judge Agent
 ├── Executor
 └── Summarizer
 ↓
Observability Layer
 ├── Structured logs
 ├── Traces
 ├── Token accounting
 ├── Risk events
 ├── Error alerts
 └── Replay records
```

## Agent 权限关系

推荐把 agent 分成四类，而不是只按名称区分：

```text
1. Thinkers：只能分析和建议
2. Producers：能生成代码、命令、patch、计划
3. Reviewers：能通过、驳回、要求修改，但不能执行
4. Actors：能执行，但不能自行决定执行
```

权限原则：

```text
普通 Agent 只有建议权
Reviewer 有否决权
Executor 有执行能力
Orchestrator 有调度权
用户有最终决定权
```

这能避免“某个 agent 生成危险命令后自己调用工具执行”的问题。

## 可变关系设计

### 1. Topology Profiles

用配置定义多种 agent 图结构：

```yaml
profiles:
  simple_answer:
    nodes: [planner, summarizer]
    edges:
      planner: [summarizer]

  safe_shell:
    nodes: [planner, shell_agent, rule_reviewer, human_approval, executor, summarizer]
    edges:
      planner: [shell_agent]
      shell_agent: [rule_reviewer]
      rule_reviewer:
        low: [executor]
        medium: [human_approval]
        high: [codex_reviewer]

  code_change:
    nodes: [planner, code_agent, test_agent, rule_reviewer, codex_reviewer, human_approval, executor]

  file_organize:
    nodes: [planner, file_agent, rule_reviewer, human_approval, executor, summarizer]

  high_risk_review:
    nodes: [planner, producer, rule_reviewer, codex_reviewer, judge, human_approval]
```

### 2. Routing Signals

Topology Router 应根据这些信号选图：

```text
task_type: answer | code | shell | file | research | mixed
risk_level: low | medium | high | extreme
target_scope: E:\agents | user_files | external_project | system_area
operation_type: read | write | move | delete | execute | install | network
uncertainty: low | medium | high
budget_mode: cheap | balanced | quality | safety
```

### 3. 动态升级

初始拓扑可以很轻，但遇到问题后升级：

```text
DeepSeek 生成命令
→ Rule Reviewer 发现批量移动
→ 升级到 file_organize + human_approval

DeepSeek 生成代码
→ 测试失败 2 次
→ 升级到 Codex review

Shell 命令涉及管理员权限
→ 升级到 high_risk_review

模型输出置信度低或格式不合格
→ 触发 Judge / Repair Agent
```

## Model Router 设计

### 路由输入

```json
{
  "task_type": "shell_command",
  "risk_level": "medium",
  "estimated_tokens": 1800,
  "requires_code_reasoning": false,
  "requires_safety_review": true,
  "history_success_rate": {
    "deepseek": 0.88,
    "codex": 0.96
  },
  "budget_mode": "balanced"
}
```

### 路由输出

```json
{
  "primary_model": "deepseek",
  "review_model": "codex",
  "fallback_model": "codex",
  "max_retry": 2,
  "reason": "medium-risk shell command requires cheap generation plus stronger review"
}
```

### 基础策略

```text
1. 默认 DeepSeek 生成
2. 本地规则先审查，不花 token
3. Codex 只在中高风险、复杂代码、失败重试、低置信度时使用
4. 同一个任务失败多次后自动升级模型
5. 记录每次模型调用的输入 token、输出 token、成本估算、耗时、结果质量
6. 后续用历史数据训练或调参路由策略
```

## 日志和预警平台

### 1. 日志分层

```text
task_log：用户任务级日志
trace_log：agent 调用链路
model_log：模型调用、token、延迟、成本
tool_log：工具调用、命令、退出码、stdout/stderr 摘要
risk_log：风险判断、审查意见、用户确认
error_log：异常、重试、降级、失败原因
audit_log：最终可追溯审计记录
```

### 2. 每个事件的最小字段

```json
{
  "event_id": "uuid",
  "task_id": "uuid",
  "run_id": "uuid",
  "timestamp": "2026-05-29T00:00:00+08:00",
  "agent": "shell_agent",
  "event_type": "command_proposed",
  "risk_level": "medium",
  "model": "deepseek-chat",
  "input_tokens": 1200,
  "output_tokens": 300,
  "cost_estimate": 0.0012,
  "latency_ms": 1800,
  "status": "ok",
  "summary": "Generated PowerShell command to list files",
  "redacted_payload_ref": "logs/payloads/..."
}
```

### 3. 预警规则

需要实时提醒：

```text
1. 高风险命令生成
2. 触碰系统目录
3. 涉及删除、覆盖、批量移动
4. 连续失败超过 N 次
5. token 成本超过预算
6. 某 agent 反复输出无效格式
7. 模型调用超时或供应商错误
8. Executor 退出码非 0
9. 审查结果与执行计划冲突
10. 日志写入失败
```

### 4. 技术建议

短期：

```text
E:\agents\logs 下写 JSONL
SQLite 保存 task/run/event 索引
简单 Web UI 展示任务、风险、错误、成本
```

中期：

```text
OpenTelemetry span 记录 agent / model / tool 调用
LangSmith 或 Phoenix 做 trace 可视化
Prometheus / Grafana 做指标和报警
```

OpenTelemetry 已有 GenAI semantic conventions，适合统一记录模型、agent、tool span。LangSmith 适合 LangChain / LangGraph 生态的 trace、debug、monitor。

## 推荐框架

### 编排

首选 LangGraph：

```text
1. 天然适合有状态图
2. 支持条件路由
3. 支持 interrupt / human-in-the-loop
4. 支持 checkpoint 和恢复
5. 适合把 agent 关系建模成图
```

### 多 agent 实现方式

不要直接用“自由群聊”。建议：

```text
1. LangGraph StateGraph 作为强控制层
2. 每个 agent 是一个 node 或 subgraph
3. Orchestrator 负责选择 profile
4. Router 根据状态决定下一条边
5. Executor 是单独节点，且必须检查 approval 和 risk gate
```

### 可观测性

```text
短期：JSONL + SQLite + 本地 dashboard
中期：OpenTelemetry + LangSmith/Phoenix
长期：规则预警 + 成本策略学习 + 质量评分
```

## MVP 范围

第一版不要做完整动态优化，先做“可配置拓扑 + 规则路由”：

```text
1. 支持 3 个 topology profile：safe_shell、code_change、file_organize
2. 支持 DeepSeek 生成
3. 支持本地 Rule Reviewer
4. 支持 Codex 审查接口占位或人工调用
5. 支持 human approval
6. Executor 默认只在 E:\agents 内写入
7. 外部路径写入、移动、删除必须确认
8. 所有事件写 JSONL
9. SQLite 记录任务索引和成本
10. 简单 CLI 或 Web UI 展示当前 run 状态
```

## 项目一句话

```text
一个以 E:\agents 为运行和审计中心、通过可配置多智能体图动态调度 DeepSeek 与 Codex 的本地安全工作流系统。
```

## 参考来源

更完整的方向拆分和论文矩阵见：`multi_agent_research_reference_map.md`。该文件按多智能体架构、动态拓扑、模型路由、安全、联网搜索、远程控制、HITL、可观测性、记忆和评测等方向分别列出参考论文与落地含义。

框架统筹和落地承载方案见：`framework_integration_decision.md`。该文件明确主框架采用 LangGraph，本地 Worker 使用 Python，云端控制台使用 FastAPI，安全策略使用本地 Policy Engine。

1. AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation, arXiv 2308.08155: https://arxiv.org/abs/2308.08155
2. A Dynamic LLM-Powered Agent Network for Task-Oriented Agent Collaboration, arXiv 2310.02170: https://arxiv.org/abs/2310.02170
3. Language Agents as Optimizable Graphs / GPTSwarm, arXiv 2402.16823: https://arxiv.org/abs/2402.16823
4. DynaSwarm: Dynamically Graph Structure Selection for LLM-based Multi-agent System, arXiv 2507.23261: https://arxiv.org/abs/2507.23261
5. FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance, arXiv 2305.05176: https://arxiv.org/abs/2305.05176
6. RouteLLM: Learning to Route LLMs with Preference Data, arXiv 2406.18665: https://arxiv.org/abs/2406.18665
7. LLM-Blender: Ensembling Large Language Models with Pairwise Ranking and Generative Fusion, arXiv 2306.02561: https://arxiv.org/abs/2306.02561
8. Mixture-of-Agents Enhances Large Language Model Capabilities, arXiv 2406.04692: https://arxiv.org/abs/2406.04692
9. LangGraph human-in-the-loop interrupts: https://langchain-ai.github.io/langgraph/how-tos/human_in_the_loop/wait-user-input/
10. LangGraph multi-agent / handoffs docs: https://docs.langchain.com/oss/python/langchain/multi-agent/handoffs
11. LangSmith Observability docs: https://docs.langchain.com/oss/python/langchain/observability
12. OpenTelemetry GenAI semantic conventions: https://opentelemetry.io/docs/specs/semconv/gen-ai/
