# SafeAgent Desktop upload bundle

This repository is being uploaded from `E:\agents` through the Codex GitHub connector because local `git push` cannot reach `github.com:443` on this machine.

The `upload-bundle/` files are base64 chunks of a Git bundle containing the local `main` branch history.

To restore after all chunks are uploaded:

```powershell
cd E:\agents
Get-Content upload-bundle\SafeAgent-Desktop-main.bundle.b64.part* -Raw | Set-Content SafeAgent-Desktop-main.bundle.b64 -NoNewline
[IO.File]::WriteAllBytes('SafeAgent-Desktop-main.bundle', [Convert]::FromBase64String((Get-Content SafeAgent-Desktop-main.bundle.b64 -Raw)))
git clone SafeAgent-Desktop-main.bundle SafeAgent-Desktop-restored
```

The normal source tree will be expanded in follow-up commits once connector-based tree upload is complete.
