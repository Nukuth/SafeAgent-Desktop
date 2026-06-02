# DeepSeek Provider Configuration

DeepSeek is configured in `configs/models.json` under the `deepseek` provider.
The checked-in config contains only safe routing metadata:

```text
provider_id = deepseek
base_url = https://api.deepseek.com/v1
model = deepseek-chat
api_key_env = SAFEAGENT_DEEPSEEK_API_KEY
```

Do not put a real DeepSeek API key in `configs/models.json`,
`configs/models.yaml`, committed docs, cloud database rows, task content, or
logs.

## Configure Locally

For a long-lived local setup, put the key in `E:\agents\.env.local`:

```text
SAFEAGENT_DEEPSEEK_API_KEY=replace-with-your-local-key
```

For a one-shell test, set it in the current PowerShell session instead:

```powershell
$env:SAFEAGENT_DEEPSEEK_API_KEY="replace-with-your-local-key"
```

Process environment variables override values from `.env.local`.

## Check Status

Run:

```powershell
cd E:\agents
.\.venv\Scripts\python.exe .\scripts\check_model_config.py
```

Expected unconfigured DeepSeek output includes:

```text
provider=deepseek enabled=True ready=False ... has_api_key=False api_key_source=missing reason=missing SAFEAGENT_DEEPSEEK_API_KEY
```

Expected configured DeepSeek output includes:

```text
provider=deepseek enabled=True ready=True ... has_api_key=True api_key_source=env reason=ready
```

The checker only prints `has_api_key=true/false` and `api_key_source`; it must
not print the actual key value.

## Probe Live Connectivity

After adding a real local key, run a real provider probe:

```powershell
cd E:\agents
.\.venv\Scripts\python.exe .\scripts\probe_model_providers.py deepseek
```

Successful output looks like:

```text
OK deepseek: model=deepseek-chat ... reply=...
```

If the key is missing, the probe must say:

```text
SKIP deepseek: ready=False reason=missing SAFEAGENT_DEEPSEEK_API_KEY
```

Treat `SKIP` as not connected. The provider code path exists, but the real
DeepSeek service has not been verified until this probe returns `OK`.

## Runtime Error

If a task routes to DeepSeek while the key is missing, the provider raises:

```text
provider.not_configured
Model provider is not configured for deepseek: missing SAFEAGENT_DEEPSEEK_API_KEY
```

The structured error details identify the missing environment variable and the
local check command. They must not include the API key value.

# Codex / GPT-5.5 Reserved Reviewer Configuration

Codex review is configured in `configs/models.json` under the `codex`
provider. It uses the OpenAI Responses API surface:

```text
provider_id = codex
type = openai_responses
base_url = https://api.openai.com/v1
model = gpt-5.5
api_key_env = SAFEAGENT_CODEX_API_KEY
```

V1 does not require this key. Configure it only when you want automatic OpenAI
API review:

```text
SAFEAGENT_CODEX_API_KEY=replace-with-your-local-openai-key
```

Then probe it:

```powershell
cd E:\agents
.\.venv\Scripts\python.exe .\scripts\probe_model_providers.py codex
```

Successful output looks like:

```text
OK codex: model=gpt-5.5 ... reply=...
```

If it prints `SKIP codex: ready=False reason=missing
SAFEAGENT_CODEX_API_KEY`, Codex is configured in the project but not yet
connected on this machine. In V1 this is acceptable: `codex_reviewer` can still
create a manual review package under `E:\agents\reviews` for use in the current
Codex conversation.
