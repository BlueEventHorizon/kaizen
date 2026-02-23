---
name: detect-python
description: |
  Detect the usable Python3 command in the current environment.
  Bypasses Claude Code shell-snapshots wrapper, detects pyenv/venv/conda.
  Other plugins should use this before running Python scripts.
  Trigger: "detect python", "python environment", "which python"
user-invocable: true
allowed-tools: Bash
argument-hint: ""
---

# /shell-utils:detect-python

## Overview

Detect the Python3 environment and output usable command path.
Handles Claude Code shell-snapshots wrapper bypass, pyenv, venv, and conda detection.

## EXECUTION RULES
- Exit plan mode if active. Do NOT ask for confirmation about plan mode.
- Always use `${CLAUDE_PLUGIN_ROOT}/scripts/detect_python.sh` to run the detection script.

## Procedure

### Step 1: Run detection

```bash
eval "$(bash ${CLAUDE_PLUGIN_ROOT}/scripts/detect_python.sh)"
```

This sets the following variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `PYTHON_CMD` | Full path or command to invoke Python3 | `/Users/name/.pyenv/shims/python3` |
| `PYTHON_VERSION` | Python version string | `3.11.5` |
| `PYTHON_WRAPPED` | Whether shell-snapshots wrapper was detected | `yes` or `no` |
| `PYTHON_ENV` | Environment type | `system`, `pyenv`, `venv`, `conda`, `none` |

### Step 2: Report results

Display the detected environment to the user:

```
Python Environment:
  Command:     $PYTHON_CMD
  Version:     $PYTHON_VERSION
  Wrapped:     $PYTHON_WRAPPED
  Environment: $PYTHON_ENV
```

## Usage from other plugins [MANDATORY]

When any plugin needs to run a Python script, it MUST first detect the Python command:

```bash
eval "$(bash ${CLAUDE_PLUGIN_ROOT}/scripts/detect_python.sh)"
$PYTHON_CMD path/to/script.py [args...]
```

Do NOT use bare `python3` — it may be wrapped by Claude Code shell-snapshots
and fail silently or behave unexpectedly.
