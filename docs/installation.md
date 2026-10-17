# Installation

## Purpose

Install Reputation Monitor 1.0 and its declared dependencies in an isolated Python environment.

## Prerequisites

- Python 3.11 or newer
- `pip`
- A terminal in the project root

## Procedure

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ".[dev]"
```

On Windows PowerShell, replace the activation command with:

```powershell
.venv\Scripts\Activate.ps1
```

Verify the installation:

```bash
reputation-monitor --help
streamlit version
python -m pytest
```

Expected result: both commands display version or usage information, and the test suite completes without failures. If a command is missing, confirm that the virtual environment is active and repeat the install command from the directory containing `pyproject.toml`.
