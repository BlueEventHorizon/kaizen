---
name: format-path
description: |
  Format file paths for readable terminal display.
  Replaces $HOME with ~, uses CWD-relative paths when shorter,
  supports middle truncation and git-root display.
  Trigger: "format path", "shorten path", "prettify path"
user-invocable: true
allowed-tools: Bash
argument-hint: "[--truncate N] [--git-root] [--shell-func] <path> [path ...]"
---

# /shell-utils:format-path

## Overview

Format file paths for readable terminal display. Provides 4 formatting modes:

| # | Feature | Example |
|---|---------|---------|
| 1 | `$HOME` → `~` | `/Users/moons/dev/proj` → `~/dev/proj` |
| 2 | CWD-relative (if shorter) | `../sibling/file` |
| 3 | Middle truncation | `~/data/dev/…/apps/CCMonitor` |
| 4 | Git root-relative | `<CCMonitor>/src/main.py` |

## EXECUTION RULES
- Exit plan mode if active. Do NOT ask for confirmation about plan mode.
- Always detect Python first using `detect_python.sh`.
- Use `${CLAUDE_PLUGIN_ROOT}/scripts/` to reference both scripts.

## Procedure

### Step 1: Detect Python and run

```bash
eval "$(bash ${CLAUDE_PLUGIN_ROOT}/scripts/detect_python.sh)"
$PYTHON_CMD ${CLAUDE_PLUGIN_ROOT}/scripts/format_path.py $ARGUMENTS
```

### Step 2: Display results

Show the formatted path(s) to the user. One path per line.

## Options

| Option | Description | Example |
|--------|-------------|---------|
| (none) | Default: `~` replacement + relative if shorter | `format_path.py /long/path` |
| `--truncate N` | Collapse middle if longer than N chars | `format_path.py --truncate 30 /path` |
| `--git-root` | Show `<repo>/relative/path` format | `format_path.py --git-root /path` |
| `--shell-func` | Output shell function definition | `format_path.py --shell-func` |

## Integration into shell scripts

### Direct call

```bash
eval "$(bash ${CLAUDE_PLUGIN_ROOT}/scripts/detect_python.sh)"
DISPLAY=$($PYTHON_CMD ${CLAUDE_PLUGIN_ROOT}/scripts/format_path.py "$TARGET_DIR")
echo "Target: $DISPLAY"
```

### Shell function (source)

```bash
eval "$($PYTHON_CMD ${CLAUDE_PLUGIN_ROOT}/scripts/format_path.py --shell-func)"
echo "Target: $(display_path "$TARGET_DIR")"
```

The `--shell-func` option outputs a lightweight bash function that performs
basic `$HOME` → `~` replacement without Python dependency.
