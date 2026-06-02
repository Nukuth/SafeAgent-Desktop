# 本地 Qwen 应急模型使用说明

## 定位

本地 Qwen 只作为应急对话和低风险推理模型使用。目标路线改为直接部署 35B/32B 级模型，但用低内存参数运行。

低内存 35B/32B 路线是：

```text
1. 直接选择 35B/32B 级 GGUF 模型。
2. 优先使用 Q4_K_M 或相近 4-bit 量化。
3. 优先使用 llama.cpp / llama-server。
4. 上下文先设小，例如 4096 或 8192。
5. 只监听 127.0.0.1，不暴露到局域网或公网。
6. 不使用 4B 作为本项目本地路线。
7. 不把 qwen3.5:27b 当作 35B/32B 替代。
8. 未经用户明确批准，不下载 20GB+ 模型文件。
```

适合：

```text
1. 断网或云 API 不可用时的本地对话。
2. 日志摘要。
3. 普通解释。
4. 低风险规划。
5. 文档整理。
```

不适合：

```text
1. 高风险命令审查。
2. 替代 Codex 审查。
3. 自动批准执行。
4. 绕过本地 PolicyEngine。
5. 直接获得 Executor 权限。
```

## 预期接口

当前项目只要求你的本地 Qwen 服务提供 OpenAI-compatible 接口：

```text
POST http://127.0.0.1:8000/v1/chat/completions
```

请求格式类似：

```json
{
  "model": "qwen-35b-local",
  "messages": [
    {"role": "user", "content": "你好"}
  ]
}
```

如果你的本地服务端口、路径或模型名不同，修改 `configs/models.json` 里的 `local_qwen`，不要把真实密钥写进配置。

## 低内存 35B/32B 部署建议

### 推荐起步方案

如果你确定直接上 35B/32B 级，建议优先选 GGUF 4-bit 量化。严格说，常见官方编码模型是 Qwen2.5-Coder-32B-Instruct-GGUF，属于 32B 级；如果你手头是 Qwen 35B / 35B-A3B GGUF，也按同样方式接入。

```text
首选量化：Q4_K_M
更省内存：Q3_K_M 或 Q2_K
更高质量：Q5_K_M，但内存压力更大
上下文：先 4096，稳定后再 8192 / 16384
并发：先 1
```

原因：

```text
1. Q4 级别能明显降低 35B/32B 的内存占用。
2. 小上下文可以避免 KV cache 把内存吃满。
3. 单并发可以降低峰值内存和卡顿。
4. 当前 SafeAgent 只需要本地模型做应急解释和低风险摘要，不需要它承担高风险审查。
```

本项目本地 Qwen 路线的硬约束：

```text
1. local_qwen 必须配置为 35B/32B 级 Qwen 模型。
2. 4B 不允许作为本项目本地路线。
3. qwen3.5:27b 不允许当作 35B/32B 替代。
4. 如果需要下载 20GB+ GGUF 文件，必须先取得用户明确批准。
```

### llama.cpp / llama-server 方向

当前建议后端是 llama.cpp 的 `llama-server`。Windows 上优先使用同一 release 里匹配 CUDA 13.x 的构建，因为本机 `nvidia-smi` 已显示 Driver 581.42 / CUDA 13.0。只有 CUDA 13.x 构建无法运行或缺失时，再提出同 release 的 CUDA 12.4 构建作为回退。

不要在未获批准时执行大模型下载。可以先完成二进制和路径检查；需要下载模型文件时，把待下载文件名、大小、来源和目标路径列出来让用户确认。

推荐把本地模型服务暴露成：

```text
http://127.0.0.1:8000/v1
```

这样 SafeAgent 不关心后端到底是 llama.cpp、LM Studio、Ollama 还是其它服务，只要兼容 `/v1/chat/completions` 即可。

如果使用 llama.cpp 的 `llama-server`，本地文件方式：

```powershell
.\llama-server.exe -m E:\agents\models\qwen-35b-local-q4.gguf --host 127.0.0.1 --port 8000 -c 4096 -np 1
```

说明：

```text
-m：GGUF 模型文件路径。
--host 127.0.0.1：只监听本机，避免暴露到局域网或公网。
--port 8000：与 SafeAgent 的默认 LOCAL_QWEN_BASE_URL 对齐。
-c 4096：低内存优先，先不要开很长上下文。
-np 1：单并发，降低峰值内存。
```

如果使用 Hugging Face 远程模型标识，并且本机 llama.cpp 支持 `-hf`，下面命令会触发模型下载；只有在用户明确批准下载 20GB+ 模型文件后才能执行：

```powershell
.\llama-server.exe -hf Qwen/Qwen2.5-Coder-32B-Instruct-GGUF:Q4_K_M --host 127.0.0.1 --port 8000 -c 4096 -np 1
```

模型文件建议放在：

```text
E:\agents\models
```

不要放到系统盘或临时下载目录。

## 配置和环境变量

模型地址和模型名在这里配置：

```text
configs/models.json
configs/models.yaml
```

默认 `local_qwen`：

```text
base_url = http://127.0.0.1:8000/v1
model = qwen-35b-local
api_key_env = SAFEAGENT_LOCAL_QWEN_API_KEY
```

PowerShell 示例只需要设置本地 key 和应急模式：

```powershell
$env:SAFEAGENT_LOCAL_QWEN_API_KEY="local-no-key"
$env:SAFEAGENT_EMERGENCY_LOCAL_MODEL="true"
```

含义：

```text
configs/models.json local_qwen.base_url：
本地 OpenAI-compatible API base URL。

configs/models.json local_qwen.model：
本地服务识别的模型名。

SAFEAGENT_LOCAL_QWEN_API_KEY：
本地服务如果不需要 key，可以保持 local-no-key。

SAFEAGENT_EMERGENCY_LOCAL_MODEL：
true 时，ModelRouter 会优先把普通推理路由到 local_qwen。
```

## 启动 worker

安装依赖后：

```powershell
cd E:\agents
$env:SAFEAGENT_CONTROL_URL="http://127.0.0.1:8080"
$env:SAFEAGENT_WORKER_TOKEN="change-me"
$env:SAFEAGENT_DEVICE_ID="local-pc-1"
$env:SAFEAGENT_WORKSPACE_ROOT="E:\agents"
$env:SAFEAGENT_EMERGENCY_LOCAL_MODEL="true"
$env:SAFEAGENT_LOCAL_QWEN_API_KEY="local-no-key"
.\.venv\Scripts\python.exe -m safeagent.local_worker.worker
```

## 当前代码状态

已经实现：

```text
1. ModelRouter 支持 emergency_local 模式。
2. emergency_local=true 时，普通任务 primary_model = local_qwen。
3. 高风险任务即使进入 local_qwen，也只能对话和解释，不能批准。
4. OpenAI-compatible 本地 provider 已有基础实现。
5. 本地 provider 连接失败会返回 upstream.transient。
```

尚未实现：

```text
1. 真实节点 handler 调用 local_qwen。
2. UI 中切换 emergency mode。
3. 模型输出参与 plan 生成。
```

## 报错处理

### 本地模型不可达

现象：

```text
upstream.transient
Local model endpoint is unreachable
```

处理：

```text
1. 确认本地 Qwen 服务已启动。
2. 确认端口和路径，例如 http://127.0.0.1:8000/v1。
3. 确认服务支持 /chat/completions。
4. 确认模型名与本地服务一致。
```

### 返回格式不兼容

现象：

```text
validation.failed
Local model response does not match OpenAI-compatible chat format
```

处理：

```text
1. 检查本地服务是否是 OpenAI-compatible。
2. 确认响应包含 choices[0].message.content。
3. 如果不是这个格式，需要后续新增专用 provider adapter。
```

## 安全边界

```text
1. local_qwen 不能替代 Codex。
2. local_qwen 不能直接调用 Executor。
3. local_qwen 不能批准高风险操作。
4. local_qwen 输出仍需经过 PolicyEngine。
5. 高风险任务仍然 blocked 或等待 Codex/人工确认。
```
