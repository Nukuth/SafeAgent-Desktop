# LangGraph Install Troubleshooting

## MSYS Python Failure

If a venv is created from:

```text
C:\msys64\ucrt64\bin\python.exe
```

installing LangGraph can fail with errors like:

```text
Failed to build uuid-utils
Failed to build ormsgpack
Unsupported platform: mingw_x86_64_ucrt_gnu
Rust not found, installing into a temporary directory
```

The cause is that the MSYS Python platform does not match the Windows wheels
needed by some LangGraph dependencies. Pip falls back to source builds and then
fails through Rust/maturin.

## Current Fix

Use the project-local Windows Python:

```text
E:\agents\.runtime\Python312
```

Create and install with:

```powershell
cd E:\agents
.\.runtime\Python312\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
```

Do not use bare `python` unless you have confirmed it is not the MSYS Python.

## Why Python Is Local To The Project

The runtime was installed under `E:\agents\.runtime` to avoid modifying the
system `PATH` or relying on administrator privileges. It should stay excluded
from source control.
