# SafeAgent Roadmap Status

本文档固定当前项目主线，避免后续实现偏离最初设想。

## 当前结论

项目方向没有改变：

```text
云端控制台只负责任务和审批
本地 Worker 主动拉取任务
本地多智能体负责规划、审查、执行边界和日志
LangGraph 负责长期核心流程编排
用户保留高风险动作最终决定权
```

当前阶段是：

```text
阶段 1：安全底座 + 本地/远程任务闭环雏形
当前完成度：约 35%-40%
```

现在已经有可扩展骨架，但还不是完整可日常使用的多智能体系统。

## 固定优先级

优先级总原则：

```text
安全 > 可控性 > 可追溯性 > LangGraph 迁移速度 > 模型效果 > 自动化程度 > UI 美观
```

LangGraph 是中期核心编排框架，但不是安全层本身。迁移到 LangGraph 时，不能因为框架接入而降低任何已有安全约束。

### P0：安全边界和错误机制

这是最高优先级，不能被 UI、模型效果或自动化速度压过去。

必须持续保证：

```text
1. server / local_worker / shared 模块边界清楚。
2. 云端不能执行本地命令。
3. 模型不能直接获得执行权限。
4. executor 是唯一真实执行边界。
5. 高风险操作必须经过本地风险判断和人工确认。
6. 所有错误必须结构化，能定位 module、code、message、details。
7. 所有关键流程必须有日志和诊断信息。
```

当前状态：

```text
已实现基础模块边界检查。
已实现统一错误 envelope。
已实现远程权限分级。
已实现 task status lifecycle。
已实现 doctor / smoke / stdlib tests。
```

下一步仍要补：

```text
配置权限升级审查。
更完整的错误码表。
更清晰的 run log 和故障定位索引。
```

不可退让的安全约束：

```text
1. 没有本地 PolicyEngine 结论，不进入 executor。
2. 没有有效 approval，不执行中高风险动作。
3. 没有匹配 plan_hash，不接受远程 approval。
4. 没有审计日志，不开放真实写入和真实执行。
5. 没有明确 allowlist，不访问 E:\agents 之外的写入路径。
6. 没有本地二次确认，不执行系统配置、安装、删除、下载后执行等操作。
7. 没有脱敏，不向云端回传日志细节。
```

### P1：LangGraph 核心编排

这是用户当前明确关心的重点，也是项目中期主骨架。

当前 `GraphRunner` 只是临时标准库实现，用来提前稳定这些语义：

```text
1. profile entry / nodes / edges。
2. 条件分支。
3. approval gate。
4. plan_hash。
5. edge decision trace。
6. 节点失败时的结构化错误。
```

后续必须迁移到 LangGraph，而不是长期停留在自写 runner。

当前运行时策略：

```text
SAFEAGENT_GRAPH_RUNTIME=auto      默认值；安装了 LangGraph 时优先使用 LangGraph。
SAFEAGENT_GRAPH_RUNTIME=langgraph 强制使用 LangGraph；不可用时直接报 dependency.missing。
SAFEAGENT_GRAPH_RUNTIME=stdlib    仅作为 fallback / 对照测试路径，不是主线。
```

LangGraph 迁移目标：

```text
1. 用 StateGraph 表达核心流程。
2. 用 TypedDict/Pydantic 定义 SafeAgentState。
3. 用 conditional edges 表达风险路由。
4. 用 interrupt() 实现 human approval。
5. 用 checkpointer 保存任务状态。
6. 保留当前 plan_hash / approval / policy / diagnostics 语义。
7. 保留当前模块隔离：LangGraph 只编排，不直接执行危险动作。
```

目标主流程：

```text
receive_task
-> planner
-> producer
-> rule_reviewer
-> risk_router
   -> low: executor
   -> medium: human_approval -> executor
   -> high: codex_reviewer -> human_approval -> executor 或 blocked
-> summarizer
-> logger
```

关键原则：

```text
LangGraph 是控制流核心。
PolicyEngine 是安全判断核心。
Executor 是执行边界。
Model providers 只提供推理能力。
UI 只展示状态和审批，不承载安全逻辑。
```

LangGraph 迁移验收条件：

```text
1. GraphRunner 当前已有安全语义必须全部保留。
2. low / medium / high / approved / review_passed 条件路由必须有测试覆盖。
3. interrupt() 只能暂停等待人工输入，不能绕过 approval validator。
4. checkpointer 只能保存状态，不能保存模型 API Key 或未脱敏敏感日志。
5. LangGraph node 不能直接执行 shell、写文件、联网或修改安全策略。
6. executor node 只能调用受控 Executor 接口。
7. 迁移前后同一个任务的 plan_hash 输入语义必须稳定或明确升级版本。
```

### P2：端到端 MVP 闭环

在 LangGraph 主骨架稳定前后，必须验证一个最小可用闭环：

```text
1. 云端提交任务。
2. 本地 Worker 拉取任务。
3. 本地选择 profile。
4. LangGraph / GraphRunner 生成计划和路径。
5. PolicyEngine 判断风险。
6. 中风险等待 approval。
7. approval 绑定 plan_hash。
8. executor dry-run。
9. 回传脱敏摘要。
10. 本地写完整日志。
```

当前状态：

```text
已有 smoke_local_flow.py 模拟中风险 approval 和高风险 blocked。
但真实 server + worker + API 运行链路仍需要更完整验收脚本。
```

### P3：模型接入

模型路线固定为：

```text
DeepSeek：高频规划、生成、总结。
Codex：高风险审查。
本地 Qwen 35B/32B：断网或 API 不可用时的应急对话和低风险推理。
```

当前状态：

```text
已有 model router 和 provider 边界。
已有 local_qwen 路线配置。
真实模型调用和错误恢复还需要完善。
```

注意：

```text
本地模型默认按 Qwen 35B/32B 级别规划。
小模型只作为排障 fallback，不作为主路线。
避免不必要下载，节省流量。
```

### P4：受控电脑操作

不能一开始开放大范围电脑操作。顺序必须是：

```text
1. dry-run。
2. live_readonly。
3. E:\agents 内文件整理。
4. 带备份的文件写入。
5. 低风险脚本执行。
6. 更高风险动作只保留说明或要求本地二次确认。
```

默认禁止：

```text
删除大量文件。
修改系统配置。
安装软件。
下载后执行。
ADB / Fastboot / 分区 / 启动项操作。
写入未知目录。
```

### P5：远程控制台和云部署

远程方案保持不变：

```text
阿里云或腾讯云轻量服务器
HTTPS
FastAPI 或 Node.js
SQLite 起步
本地 Worker polling
不做内网穿透
不暴露本地端口
```

但 UI 和部署不是当前最高优先级。

正确顺序是：

```text
先安全和 LangGraph。
再端到端闭环。
再做远程 UI。
最后做云部署脚本和运维文档。
```

### P6：知识库和长期扩展

RAG、教程检索、长期记忆、agent 自动添加属于后续增强。

前提是：

```text
1. 权限模型稳定。
2. LangGraph 主流程稳定。
3. 日志和审批可靠。
4. 配置变更可审查。
```

## 与最初设想的对齐表

| 最初设想 | 当前状态 | 判断 |
| --- | --- | --- |
| 云端只做控制平面 | server 已按任务队列和审批设计 | 对齐 |
| 本地 Worker 主动轮询 | worker/client 已有雏形 | 对齐 |
| 模型不直接执行命令 | provider 与 executor 分离 | 对齐 |
| 多 agent 可扩展 | agents/profile 配置已存在 | 部分完成 |
| LangGraph 为长期核心 | 目前用 GraphRunner 临时稳定语义 | 方向对齐，需迁移 |
| 高风险需要审查和确认 | policy/approval/plan_hash 已有 | 部分完成 |
| 清晰报错机制 | ErrorEnvelope/diagnostics 已有 | 部分完成 |
| 日志完整可追溯 | build log、events、diagnostics 已有 | 仍需增强 |
| 可远程使用且不内网穿透 | polling 架构已确定 | 部分完成 |
| 本地 Qwen 35B 应急 | 文档和 provider 路线已预留 | 部分完成 |

## 下一阶段执行顺序

短期不继续扩散功能，按以下顺序推进：

```text
1. 固化配置权限升级审查。
2. 写 LangGraph 迁移设计文档。
3. 增加 SafeAgentState 定义。
4. 做 LangGraph 版最小流程原型。
5. 对比 GraphRunner 和 LangGraph 输出，确保语义一致。
6. 接入 human interrupt / checkpointer。
7. 再扩展真实模型调用和端到端验收。
```

## 不做的偏移方向

```text
1. 不优先做普通聊天 UI。
2. 不优先做很多 agent 名字。
3. 不让 agent 自由互相对话。
4. 不绕过 LangGraph 直接堆脚本。
5. 不把云服务器变成本地命令执行器。
6. 不为了演示效果提前开放危险电脑操作。
7. 不把 OpenClaw 作为主线绑定。
```

## 当前一句话路线

```text
先用现有 GraphRunner 稳住安全语义，再把核心流程迁移到 LangGraph，
最后在这个受控状态机上接模型、接远程控制台、接有限电脑操作。
```
