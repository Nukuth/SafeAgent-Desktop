# 多智能体系统研究方向与参考论文矩阵

## 目的

这份文档补充 `multi_agent_architecture_research.md`，按项目需要把相关研究方向拆开，并分别给出可继续阅读的论文、标准和落地结论。

框架选型和各方向如何统筹到工程实现，见：`framework_integration_decision.md`。

当前项目目标不是复现某篇论文，而是构建一个：

```text
以 E:\agents 为本地运行与审计中心，
以阿里云 / 腾讯云轻量服务器为远程控制平面，
通过可配置 profile 动态组织 agent，
通过 DeepSeek / Codex 分流控制成本与风险，
通过日志、预警、审批和安全网关约束真实电脑操作的多智能体系统。
```

## 方向 1：多智能体总体架构与协作框架

核心问题：

```text
多个 agent 是否应该自由聊天？
还是应该被 Orchestrator 以图结构调度？
固定角色流水线和动态协作图分别适合什么阶段？
```

结论：

```text
MVP 采用固定 profile。
长期采用可配置动态图。
禁止无约束群聊式 agent 协作。
```

参考论文：

1. AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation, arXiv:2308.08155  
   https://arxiv.org/abs/2308.08155
2. CAMEL: Communicative Agents for Mind Exploration of Large Language Model Society, arXiv:2303.17760  
   https://arxiv.org/abs/2303.17760
3. MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework, arXiv:2308.00352  
   https://arxiv.org/abs/2308.00352
4. ChatDev: Communicative Agents for Software Development, arXiv:2307.07924  
   https://arxiv.org/abs/2307.07924
5. A Survey on Large Language Model based Multi-Agent Systems, arXiv:2402.01680  
   https://arxiv.org/abs/2402.01680

对本项目的含义：

```text
AutoGen/CAMEL 证明多 agent 对话有用，但也提示必须控制上下文和角色边界。
MetaGPT/ChatDev 说明固定角色流水线适合工程任务。
本项目应吸收“角色明确”的优点，避免“自由对话失控”的缺点。
```

## 方向 2：可变 agent 关系、动态拓扑与自动生成 agent

核心问题：

```text
后续能不能自动添加 agent？
agent 之间的关系能不能按任务动态变化？
profile 到底是什么？
```

结论：

```text
profile = agent 协作拓扑模板。
第一版采用半自动 agent 注册 + 可配置 profile。
后期再做运行时动态改图和历史数据驱动的拓扑优化。
```

参考论文：

1. DyLAN: A Dynamic LLM-Powered Agent Network for Task-Oriented Agent Collaboration, arXiv:2310.02170  
   https://arxiv.org/abs/2310.02170
2. GPTSwarm: Language Agents as Optimizable Graphs, arXiv:2402.16823  
   https://arxiv.org/abs/2402.16823
3. AFlow: Automating Agentic Workflow Generation, arXiv:2410.10762  
   https://arxiv.org/abs/2410.10762
4. AutoAgents: A Framework for Automatic Agent Generation, arXiv:2309.17288  
   https://arxiv.org/abs/2309.17288
5. AgentVerse: Facilitating Multi-Agent Collaboration and Exploring Emergent Behaviors, arXiv:2308.10848  
   https://arxiv.org/abs/2308.10848
6. DynaSwarm: Dynamically Graph Structure Selection for LLM-based Multi-agent System, arXiv:2507.23261  
   https://arxiv.org/abs/2507.23261  
   注：该 arXiv 页面已标记 withdrawn，只作为“动态选图”研究方向线索，不应作为工程决策的主要证据。

对本项目的含义：

```text
不要把流程写死成 Planner -> Coder -> Reviewer -> Executor。
应该维护 Agent Registry 和 Profile Registry。
Topology Router 根据任务类型、风险、网络模式、预算选择 profile。
自动生成 agent 可以做，但必须先进入待审核 registry，不能自动获得工具、网络或执行权限。
```

## 方向 3：模型路由、级联推理与 token 成本优化

核心问题：

```text
DeepSeek 和 Codex 怎么分工？
如何最大化性价比？
什么时候升级到更强或更贵模型？
```

结论：

```text
DeepSeek 默认负责生成、总结、普通分析。
Codex 负责高风险审查、复杂 diff、危险命令、失败升级。
本地规则先跑，能不用模型就不用模型。
```

参考论文：

1. FrugalGPT: How to Use Large Language Models While Reducing Cost and Improving Performance, arXiv:2305.05176  
   https://arxiv.org/abs/2305.05176
2. RouteLLM: Learning to Route LLMs with Preference Data, arXiv:2406.18665  
   https://arxiv.org/abs/2406.18665
3. LLM-Blender: Ensembling Large Language Models with Pairwise Ranking and Generative Fusion, arXiv:2306.02561  
   https://arxiv.org/abs/2306.02561
4. Mixture-of-Agents Enhances Large Language Model Capabilities, arXiv:2406.04692  
   https://arxiv.org/abs/2406.04692

对本项目的含义：

```text
Model Router 需要记录每次调用的模型、token、成本、延迟、成功率和失败原因。
一开始使用规则路由。
积累日志后再用历史任务质量和成本数据优化路由。
不要每一步都上 Codex，也不要让 DeepSeek 直接处理高风险执行决策。
```

## 方向 4：工具调用、命令生成与受限执行

核心问题：

```text
LLM 怎么调用工具？
命令和真实执行如何分离？
如何防止模型自己越权执行？
```

结论：

```text
agent 可以提出 tool call。
Executor 才能真实执行。
工具权限必须按 agent 显式声明。
下载、写入、执行必须拆成不同权限。
```

参考论文：

1. ReAct: Synergizing Reasoning and Acting in Language Models, arXiv:2210.03629  
   https://arxiv.org/abs/2210.03629
2. Toolformer: Language Models Can Teach Themselves to Use Tools, arXiv:2302.04761  
   https://arxiv.org/abs/2302.04761
3. Gorilla: Large Language Model Connected with Massive APIs, arXiv:2305.15334  
   https://arxiv.org/abs/2305.15334
4. ToolLLM: Facilitating Large Language Models to Master 16000+ Real-world APIs, arXiv:2307.16789  
   https://arxiv.org/abs/2307.16789

对本项目的含义：

```text
Shell Agent 只生成 CommandProposal。
Rule Reviewer 评估风险。
Human Approval 决定是否允许。
Executor 执行前再次检查 profile、approval、network_mode、path_policy。
```

## 方向 5：安全、提示注入、间接攻击与多 agent 感染

核心问题：

```text
联网搜索和读取网页时，外部内容可能携带恶意指令。
一个 agent 被污染后，是否会影响其它 agent？
模型输出能不能当成安全边界？
```

结论：

```text
系统提示不是安全边界。
外部内容必须当作不可信数据。
Search Agent 的结果不能直接进入 Executor。
高风险工具调用必须经过本地规则、Codex 和人工确认。
```

参考论文：

1. AgentDojo: A Dynamic Environment to Evaluate Attacks and Defenses for LLM Agents, arXiv:2406.13352  
   https://arxiv.org/abs/2406.13352
2. InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated Large Language Model Agents, arXiv:2403.02691  
   https://arxiv.org/abs/2403.02691
3. Prompt Infection: LLM-to-LLM Prompt Injection within Multi-Agent Systems, arXiv:2410.07283  
   https://arxiv.org/abs/2410.07283
4. AgentHarm: A Benchmark for Measuring Harmfulness of LLM Agents, arXiv:2410.09024  
   https://arxiv.org/abs/2410.09024
5. Securing AI Agents with Information-Flow Control, Microsoft Research  
   https://www.microsoft.com/en-us/research/publication/securing-ai-agents-with-information-flow-control/
6. Ghost in the Agent: Redefining Information Flow Tracking for LLM Agents, arXiv:2604.23374  
   https://arxiv.org/abs/2604.23374

经典安全基础：

1. The Protection of Information in Computer Systems, Saltzer and Schroeder, 1975  
   https://web.cs.wpi.edu/~cs557/f14/papers/saltzer1975_alt.html
2. NIST SP 800-207: Zero Trust Architecture  
   https://www.nist.gov/publications/zero-trust-architecture-0

对本项目的含义：

```text
权限默认拒绝。
每次工具调用都要重新授权。
联网内容进入系统时打上 untrusted 标记。
untrusted 内容不能直接影响 shell、file write、delete、approval。
高风险操作需要分离权限：agent 建议、reviewer 审查、用户确认、executor 执行。
```

## 方向 6：联网搜索、RAG 与资料可信度

核心问题：

```text
系统需要联网搜索，但不能让搜索结果污染执行链。
什么时候检索？
检索结果如何引用、记录、过滤？
```

结论：

```text
只有 Search Agent 默认可联网。
搜索必须记录 query、URL、时间、摘要、引用和风险。
下载文件只能进入 E:\agents\downloads，且不能自动执行。
```

参考论文：

1. Retrieval-Augmented Generation for Large Language Models: A Survey, arXiv:2312.10997  
   https://arxiv.org/abs/2312.10997
2. Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection, arXiv:2310.11511  
   https://arxiv.org/abs/2310.11511
3. Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models through Question Complexity, arXiv:2403.14403  
   https://arxiv.org/abs/2403.14403
4. From Local to Global: A Graph RAG Approach to Query-Focused Summarization, arXiv:2404.16130  
   https://arxiv.org/abs/2404.16130

对本项目的含义：

```text
普通任务不自动联网。
research profile 才启用 search_allowed。
复杂问题才检索，简单问题不检索，避免浪费 token。
RAG 输出必须带引用，不能只给“模型记忆”。
```

## 方向 7：远程控制平面、零信任与 API 安全

核心问题：

```text
不做内网穿透、不做远程桌面，如何远程使用 agent？
云服务器能不能直接控制本地电脑？
```

结论：

```text
使用阿里云 / 腾讯云轻量服务器作为控制平面。
本地 Worker 主动轮询云端任务队列。
云端不能直接执行命令，不能保存模型 API Key。
```

参考资料：

1. NIST SP 800-207: Zero Trust Architecture  
   https://www.nist.gov/publications/zero-trust-architecture-0
2. OWASP API Security Top 10  
   https://owasp.org/API-Security/
3. Saltzer and Schroeder: The Protection of Information in Computer Systems  
   https://web.cs.wpi.edu/~cs557/f14/papers/saltzer1975_alt.html

对本项目的含义：

```text
远程浏览器 -> 云端控制台 -> 任务队列 -> 本地 Worker 主动拉取。
云端 approval 只能批准当前 plan，且必须过期。
本地 Worker 离线时，云端只能显示离线，不能代替执行。
```

## 方向 8：Human-in-the-loop、审批流与可控自动化

核心问题：

```text
哪些步骤必须人工确认？
远程批准是否足够？
如何防止“审批按钮”变成形式主义？
```

结论：

```text
审批不是最后一个按钮，而是风险分级流程的一部分。
中风险可远程 approval。
高风险需要本地二次确认。
极高风险默认只给建议，不执行。
```

参考论文：

1. LLM-Based Human-Agent Collaboration and Interaction Systems: A Survey, arXiv:2505.00753  
   https://arxiv.org/abs/2505.00753
2. HMCF: A Human-in-the-loop Multi-Robot Collaboration Framework Based on Large Language Models, arXiv:2505.00820  
   https://arxiv.org/abs/2505.00820
3. Testing Language Model Agents Safely in the Wild, arXiv:2311.10538  
   https://arxiv.org/abs/2311.10538
4. On Scalable Oversight with Weak LLMs Judging Strong LLMs, arXiv:2407.04622  
   https://arxiv.org/abs/2407.04622

对本项目的含义：

```text
approval 对象必须包含 approval_scope 和 expires_at。
批准只对当前 plan hash 有效。
计划变化后必须重新审批。
用户能看到命令、路径、风险、审查结果和回滚建议。
```

## 方向 9：日志、可观测性、错误预警与 LLMOps

核心问题：

```text
如何知道 agent 为什么失败？
如何追踪 token 成本？
如何在危险操作发生前预警？
```

结论：

```text
每个 run 必须记录 task、profile、agent、model、tool、risk、approval、cost。
本地保存完整日志。
云端只保存脱敏摘要。
预警比事后总结更重要。
```

参考论文与标准：

1. AI Observability for Large Language Model Systems: A Multi-Layer Analysis of Monitoring Approaches from Confidence Calibration to Infrastructure Tracing, arXiv:2604.26152  
   https://arxiv.org/abs/2604.26152
2. AgentTrace: A Structured Logging Framework for Agent System Observability, OpenReview  
   https://openreview.net/pdf/a60321c00cd103370cbb74aa114dc105cda342be.pdf
3. PrefixGuard: From LLM-Agent Traces to Online Failure-Warning Monitors, arXiv:2605.06455  
   https://arxiv.org/abs/2605.06455
4. OpenTelemetry GenAI Semantic Conventions  
   https://opentelemetry.io/docs/specs/semconv/gen-ai/

对本项目的含义：

```text
短期：JSONL + SQLite + 本地 dashboard。
中期：OpenTelemetry spans + Prometheus/Grafana 或 LangSmith/Phoenix。
预警规则包括：高风险命令、外部路径写入、连续失败、token 超预算、模型输出格式错误、审批过期、下载后执行尝试。
```

## 方向 10：长期记忆、状态管理与技能库

核心问题：

```text
agent 如何积累经验？
哪些内容能进入长期记忆？
如何防止被污染的记忆影响后续执行？
```

结论：

```text
长期记忆必须区分事实、偏好、执行记录、技能、失败案例。
外部网页和模型输出不能直接写入高信任记忆。
技能库必须经过测试和审查后启用。
```

参考论文：

1. MemGPT: Towards LLMs as Operating Systems, arXiv:2310.08560  
   https://arxiv.org/abs/2310.08560
2. Generative Agents: Interactive Simulacra of Human Behavior, arXiv:2304.03442  
   https://arxiv.org/abs/2304.03442
3. Reflexion: Language Agents with Verbal Reinforcement Learning, arXiv:2303.11366  
   https://arxiv.org/abs/2303.11366
4. Voyager: An Open-Ended Embodied Agent with Large Language Models, arXiv:2305.16291  
   https://arxiv.org/abs/2305.16291

对本项目的含义：

```text
可以建立 skill library，但不要让 skill 自动获得执行权限。
失败经验可进入 low-trust memory。
被 Codex 审查过、测试通过的脚本或流程才能进入 high-trust skill library。
记忆写入也要有审计日志。
```

## 方向 11：评测、基准测试与真实电脑任务

核心问题：

```text
如何判断系统是否真的更好？
如何评估电脑操作、代码修改、网页操作和 agent 任务完成率？
```

结论：

```text
不要只用“模型回答看起来不错”评估。
需要任务成功率、失败率、人工介入次数、风险拦截率、token 成本、执行耗时。
```

参考论文：

1. AgentBench: Evaluating LLMs as Agents, arXiv:2308.03688  
   https://arxiv.org/abs/2308.03688
2. WebArena: A Realistic Web Environment for Building Autonomous Agents, arXiv:2307.13854  
   https://arxiv.org/abs/2307.13854
3. OSWorld: Benchmarking Multimodal Agents for Open-Ended Tasks in Real Computer Environments, arXiv:2404.07972  
   https://arxiv.org/abs/2404.07972
4. SWE-bench: Can Language Models Resolve Real-World GitHub Issues?, arXiv:2310.06770  
   https://arxiv.org/abs/2310.06770

对本项目的含义：

```text
MVP 验收不要追求完全自动化。
先评估：任务分类是否正确、profile 是否选对、风险是否拦截、日志是否完整、成本是否可解释。
后续再引入真实电脑任务集和回放测试。
```

## 方向 12：代码修改、代码审查与软件工程 agent

核心问题：

```text
如何安全地让 agent 修改项目代码？
如何避免无意义重构、破坏用户改动、生成不可维护代码？
```

结论：

```text
代码修改必须走 diff 审查。
复杂 diff 或跨模块修改升级到 Codex。
Executor 不能自动提交代码。
```

参考论文：

1. SWE-bench: Can Language Models Resolve Real-World GitHub Issues?, arXiv:2310.06770  
   https://arxiv.org/abs/2310.06770
2. SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering, arXiv:2405.15793  
   https://arxiv.org/abs/2405.15793
3. MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework, arXiv:2308.00352  
   https://arxiv.org/abs/2308.00352
4. ChatDev: Communicative Agents for Software Development, arXiv:2307.07924  
   https://arxiv.org/abs/2307.07924

对本项目的含义：

```text
Code Agent 只生成 PatchProposal。
Test Agent 运行可控测试。
Codex Reviewer 审查复杂 diff。
Summarizer 输出改动、测试结果和残余风险。
```

## 建议的近期设计优先级

按实现价值排序：

```text
P0：安全边界
- Agent Registry
- Profile Registry
- Risk Router
- Network Policy Router
- Human Approval
- Local Executor

P1：远程控制
- 阿里云 / 腾讯云控制台
- 本地 Worker polling
- 脱敏日志回传
- heartbeat

P2：成本优化
- Model Router
- token/cost ledger
- DeepSeek -> Codex fallback

P3：可观测性
- JSONL
- SQLite event index
- error alerts
- run replay

P4：动态扩展
- 半自动 agent 注册
- profile marketplace
- 历史质量评分
- 动态拓扑优化
```

## 最终架构约束

```text
1. agent 可以建议，但不能越权执行。
2. profile 决定 agent 关系、网络模式和风险门。
3. Router 决定选哪个 profile 和模型。
4. Search Agent 是默认唯一可联网搜索的 agent。
5. Executor 是默认唯一可执行命令的组件。
6. 云服务器只做控制平面，不保存模型 API Key，不直接控制电脑。
7. 高风险操作必须 Codex 审查 + 用户确认。
8. 任何自动添加的 agent 都必须先审核，不能自动获得网络或执行权限。
```
