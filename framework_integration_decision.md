# 多智能体系统框架统筹决策

## 结论

本项目建议采用 **Python-first、LangGraph-core、FastAPI-control-plane** 的组合。

核心决策：

```text
1. 本地多智能体编排核心：LangGraph
2. 云端远程控制台：FastAPI + SQLite/Postgres + Web UI
3. 本地 Worker：Python asyncio/httpx polling
4. Agent/Profile/Router 配置：YAML/JSON + Pydantic 校验
5. 风险、网络、路径、审批策略：本地确定性 Policy Engine
6. 模型调用：DeepSeek / Codex 由 Model Router 统一调度
7. 日志与预警：JSONL + SQLite 起步，OpenTelemetry 后续接入
8. OpenAI Agents SDK：作为 Codex 审查、guardrail、tracing 的可选适配层，不作为第一版总编排核心
9. AutoGen/CrewAI/MetaGPT：作为参考框架，不作为第一版底座
```

最重要的判断：

```text
LangGraph 负责“流程控制和状态机”。
FastAPI 负责“远程入口和任务队列”。
Policy Engine 负责“安全边界”。
模型只负责“生成、分析、审查建议”，不能负责最终放行。
```

## 为什么核心选 LangGraph

项目需要的是：

```text
1. 可配置 agent 图
2. 条件路由
3. human-in-the-loop
4. 可暂停、可恢复
5. 持久化状态
6. 任务运行记录
7. 动态 profile 编译
8. 明确边界的 Executor
```

LangGraph 比 AutoGen / CrewAI 更适合作为核心，因为它更像“有状态工作流图”，而不是“agent 群聊框架”。本项目要避免自由群聊式协作，优先使用可控图结构。

推荐抽象：

```text
Profile Registry
  ↓
Graph Compiler
  ↓
LangGraph StateGraph
  ↓
Runnable Agent Graph
```

每个 profile 编译为一个 LangGraph 子图：

```text
safe_shell
file_organize
code_change
research
high_risk_review
```

## 分层架构

```text
Remote Browser
 ↓
Cloud Control Plane
 FastAPI / Web UI / Task Queue / Redacted Logs
 ↓ HTTPS polling
Local Worker under E:\agents
 ↓
Local Runtime
 ├── Orchestrator
 ├── Profile Registry
 ├── Agent Registry
 ├── Topology Router
 ├── Model Router
 ├── Risk Router
 ├── Network Policy Router
 ├── Human Approval Gate
 ├── Executor
 └── Observability Layer
 ↓
LangGraph Dynamic Agent Graph
 ├── Planner
 ├── Search Agent
 ├── File Agent
 ├── Code Agent
 ├── Shell Agent
 ├── Rule Reviewer
 ├── Codex Reviewer
 ├── Judge
 └── Summarizer
```

## 框架职责表

| 方向 | 推荐框架/组件 | 原因 |
|---|---|---|
| 多智能体编排 | LangGraph | 图结构、条件边、状态、暂停恢复、HITL |
| 远程控制台 | FastAPI | 简单、Python 生态一致、适合 REST API |
| 云端部署 | 阿里云/腾讯云轻量服务器 + Docker Compose | 可控、迁移简单、国内访问更现实 |
| HTTPS | Caddy 或 Nginx | 反向代理、证书、基础安全头 |
| 云端数据库 | SQLite MVP，Postgres 后续 | MVP 简单，后续可扩展 |
| 本地状态库 | SQLite | 任务索引、run、event、approval、成本 ledger |
| 本地完整日志 | JSONL | 可追加、易审计、易回放 |
| 配置 schema | Pydantic | 校验 agent/profile/router 配置 |
| 配置文件 | YAML/JSON | 人能读，适合 profile registry |
| 本地 Worker 通信 | httpx + asyncio polling | 不暴露本地端口，穿透校园网 NAT |
| 模型调用 | OpenAI-compatible HTTP client + provider adapters | DeepSeek/Codex 统一路由 |
| 安全策略 | Python Policy Engine | 本地确定性规则优先，不依赖模型判断安全 |
| 可观测性 | JSONL/SQLite 起步，OpenTelemetry 后续 | 先落地，后接标准 tracing |
| Web UI | FastAPI templates + HTMX MVP | 避免前期 React 工程复杂度 |

## 为什么不以 AutoGen / CrewAI 为核心

AutoGen、CrewAI 适合快速搭多 agent demo，但本项目的核心矛盾不是“agent 能不能聊天”，而是：

```text
1. 真实电脑操作的安全边界
2. 远程使用时的审批链
3. 联网内容污染隔离
4. 模型成本分流
5. 可审计运行记录
6. 可暂停恢复
7. profile 可配置拓扑
```

因此 AutoGen / CrewAI 可以作为参考或某些 agent 的内部实现方式，但不能作为第一版总控层。

## OpenAI Agents SDK 的位置

OpenAI Agents SDK 适合：

```text
1. 把 Codex Reviewer 包成一个审查 agent
2. 使用 handoff 表达专业审查转交
3. 使用 guardrail 表达输入/输出边界
4. 使用 tracing 辅助调试模型调用
5. 把可复用流程沉淀成 Codex skill
```

但第一版不建议用它替代 LangGraph 总编排。原因：

```text
LangGraph 更适合作为跨模型、跨工具、跨审批状态的状态机。
OpenAI Agents SDK 更适合作为 OpenAI/Codex 侧能力适配层。
```

推荐关系：

```text
LangGraph node
  ↓
Codex Reviewer Adapter
  ↓
OpenAI Agents SDK / Codex call
```

## 核心数据结构

### Agent Registry

```yaml
agents:
  shell_agent:
    role: producer
    model_policy: deepseek_default
    tools: []
    permissions:
      can_execute: false
      can_write: false
    network:
      allowed: false

  search_agent:
    role: producer
    model_policy: deepseek_default
    tools: [web_search]
    permissions:
      can_execute: false
      can_write: false
    network:
      allowed: true
      mode: search_only
      can_download: false

  executor:
    role: actor
    model_policy: none
    permissions:
      can_execute: true
      can_write: true
    network:
      allowed: false
```

### Profile Registry

```yaml
profiles:
  safe_shell:
    network_mode: api_only
    remote_allowed: true
    nodes:
      - planner
      - shell_agent
      - rule_reviewer
      - human_approval
      - executor
      - summarizer
    edges:
      planner: shell_agent
      shell_agent: rule_reviewer
      rule_reviewer.low: executor
      rule_reviewer.medium: human_approval
      rule_reviewer.high: codex_reviewer
      human_approval.approved: executor
      executor: summarizer

  research:
    network_mode: search_allowed
    remote_allowed: true
    nodes:
      - planner
      - search_agent
      - summarizer
```

### Run State

```json
{
  "task_id": "uuid",
  "run_id": "uuid",
  "source": "local|remote",
  "profile": "safe_shell",
  "network_mode": "api_only",
  "risk_level": "medium",
  "approval_status": "pending",
  "model_calls": [],
  "tool_calls": [],
  "events": [],
  "summary": null
}
```

## 统筹流程

### 远程任务

```text
1. 用户在阿里云/腾讯云控制台提交任务
2. 云端写入 task queue
3. 本地 Worker 主动 polling
4. 本地 Task Classifier 判断任务类型
5. Topology Router 选择 profile
6. Network Policy Router 检查是否允许联网
7. Model Router 选择 DeepSeek / Codex
8. LangGraph 执行当前 profile
9. Rule Reviewer / Risk Router 给出风险等级
10. 需要时进入 human approval
11. Executor 执行被放行的动作
12. 本地写完整 JSONL/SQLite 日志
13. 云端只接收脱敏摘要和状态
```

### 联网搜索

```text
1. 只有 research profile 或显式 search_allowed 才能联网
2. 只有 Search Agent 能访问 web_search
3. 搜索结果标记为 untrusted
4. untrusted 内容不能直接生成可执行命令
5. 下载必须切换到 download_guarded
6. 下载文件只能进入 E:\agents\downloads
7. 下载后执行必须重新审批
```

### 高风险操作

```text
1. Rule Reviewer 先用本地规则识别风险
2. 高风险升级 Codex Reviewer
3. Codex 只能建议通过/拒绝/替代方案
4. Human Approval 必须显示命令、路径、风险、回滚建议
5. Executor 执行前复核 approval_scope、plan_hash、expires_at
6. 计划变化后旧 approval 作废
```

## MVP 实现顺序

```text
阶段 1：本地核心
- Agent Registry
- Profile Registry
- Policy Engine
- LangGraph profiles
- JSONL/SQLite logs

阶段 2：远程控制
- FastAPI task API
- 本地 Worker polling
- heartbeat
- redacted event upload
- approval API

阶段 3：模型分流
- DeepSeek adapter
- Codex reviewer adapter
- cost ledger
- retry/fallback rules

阶段 4：联网搜索
- Search Agent
- search_allowed mode
- citation logging
- untrusted content tagging

阶段 5：预警与看板
- risk alerts
- failed run dashboard
- token budget dashboard
- lockdown mode
```

## 已安装的 Codex skills

已从 OpenAI 官方 `openai/skills` 仓库安装：

```text
security-threat-model
security-best-practices
security-ownership-map
```

已从 LangChain 官方 `langchain-ai/langchain-skills` 仓库安装：

```text
framework-selection
langchain-fundamentals
langchain-dependencies
langchain-middleware
langchain-rag
langgraph-fundamentals
langgraph-human-in-the-loop
langgraph-persistence
deep-agents-core
deep-agents-orchestration
deep-agents-memory
```

已从第三方 `proflead/codex-skills-library` 仓库安装一组轻量 coding workflow skills。安装前检查了对应 `SKILL.md`，它们偏流程指导，不授予工具权限，也不要求自动执行命令：

```text
codebase-orientation
debugging-checklist
error-message-explainer
architecture-review
pr-reviewer
refactor-roadmap
simple-refactor
bug-repro-plan
unit-test-starter
integration-test-planner
ci-failure-triage
observability-setup
```

用途：

```text
security-threat-model：
后续为本项目生成仓库级威胁模型，识别资产、边界、攻击路径和缓解措施。

security-best-practices：
后续实现 FastAPI / Python / JavaScript 代码时，提供安全默认实践检查。

security-ownership-map：
等项目进入 git 仓库并有提交历史后，用于分析安全敏感代码的真实维护者和 bus factor。

framework-selection：
在 LangGraph、OpenAI Agents SDK、AutoGen、CrewAI、普通 FastAPI/Worker 之间做框架取舍时提供参考。

langchain-fundamentals / langchain-dependencies：
后续写 LangChain/LangGraph 代码时减少依赖、包名、初始化方式上的低级错误。

langgraph-fundamentals / langgraph-human-in-the-loop / langgraph-persistence：
直接服务本项目核心：可配置图、人工审批、暂停恢复、checkpoint、thread_id、长期/短期状态。

langchain-middleware：
用于把日志、限流、上下文裁剪、模型调用前后处理等横切逻辑做成中间件。

langchain-rag：
用于后续 Search Agent、本地知识库、论文/文档检索和引用式回答。

deep-agents-core / deep-agents-orchestration / deep-agents-memory：
用于提升大任务能力，包括子任务拆解、subagent 委派、todo 追踪、长程记忆和 human-in-the-loop。

codebase-orientation / architecture-review：
用于新项目快速摸清入口、模块、运行方式，并对系统设计做可维护性与可靠性审查。

debugging-checklist / error-message-explainer / bug-repro-plan：
用于把报错处理成可复现、可定位、可验证的调试流程，减少盲目修改。

pr-reviewer / refactor-roadmap / simple-refactor：
用于代码审查、重构拆分和降低大改风险。

unit-test-starter / integration-test-planner / ci-failure-triage：
用于补齐测试、集成验证和 CI 失败定位。

observability-setup：
用于设计日志、指标、trace 和告警，和本项目的预警平台目标直接相关。
```

注意：

```text
需要重启 Codex 才能在技能列表中自动识别新安装 skills。
本轮已经可以通过文件读取确认安装成功，但运行时 skill 触发通常要等重启。
```

## 后续不建议现在安装的 skills

```text
部署类 skill：
暂时不装，等确定阿里云/腾讯云部署方式后再补。

UI/设计类 skill：
当前重点是安全架构，不优先。

第三方来源 skill：
只安装了 `proflead/codex-skills-library` 中已检查且与 coding workflow 直接相关的轻量技能。未安装 prompt 优化、写作、前端样式、泛化工具类技能，避免扩大技能噪声和信任面。
```

## 最终框架选择

```text
主框架：LangGraph
服务框架：FastAPI
配置校验：Pydantic
本地存储：SQLite + JSONL
远程部署：阿里云/腾讯云轻量服务器 + Docker Compose
模型分流：自写 Model Router
安全策略：自写 Policy Engine
可观测性：JSONL/SQLite 起步，OpenTelemetry 后续
Codex 能力增强：官方 security skills + 可选 OpenAI Agents SDK adapter
```

这个组合的重点不是“最炫”，而是可控、可审计、容易落地，并且不会把真实电脑操作安全边界交给模型或云端。
