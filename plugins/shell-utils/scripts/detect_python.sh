#!/usr/bin/env bash
# detect_python.sh - Detect Python3 environment for Claude Code plugins
# Created by k_terada
#
# Detects the usable Python3 command, bypassing Claude Code shell-snapshots
# wrapper if present. Outputs eval-able variable assignments.
#
# Usage:
#   eval "$(path/to/detect_python.sh)"
#   $PYTHON_CMD script.py
#
# Output variables:
#   PYTHON_CMD      - Full path or command to invoke Python3
#   PYTHON_VERSION  - Python version string (e.g., 3.11.5)
#   PYTHON_WRAPPED  - "yes" if shell-snapshots wrapper was detected
#   PYTHON_ENV      - Environment type: system, pyenv, venv, conda

set -euo pipefail

detect_python() {
    local python_cmd=""
    local python_wrapped="no"
    local python_env="system"
    local python_version=""

    # 1. Check for Claude Code shell-snapshots wrapper
    if [[ -d "$HOME/.claude/shell-snapshots" ]] && \
       [[ -n "$(ls -A "$HOME/.claude/shell-snapshots" 2>/dev/null)" ]]; then
        # Shell wrapper likely present: use /usr/bin/which to get real path
        python_cmd=$(/usr/bin/which python3 2>/dev/null || true)
        if [[ -n "$python_cmd" ]]; then
            python_wrapped="yes"
        fi
    fi

    # 2. Fallback: find python3 normally
    if [[ -z "$python_cmd" ]]; then
        python_cmd=$(command -v python3 2>/dev/null || true)
    fi

    # 3. Last resort
    if [[ -z "$python_cmd" ]]; then
        echo "# ERROR: python3 not found" >&2
        echo 'PYTHON_CMD=""'
        echo 'PYTHON_VERSION=""'
        echo 'PYTHON_WRAPPED="no"'
        echo 'PYTHON_ENV="none"'
        return 1
    fi

    # 4. Get version
    python_version=$("$python_cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>/dev/null || echo "unknown")

    # 5. Detect environment type
    if [[ -n "${VIRTUAL_ENV:-}" ]]; then
        python_env="venv"
    elif [[ -n "${CONDA_DEFAULT_ENV:-}" ]]; then
        python_env="conda"
    elif [[ "$python_cmd" == *".pyenv/"* ]]; then
        python_env="pyenv"
    fi

    # Output eval-able assignments
    echo "PYTHON_CMD=\"$python_cmd\""
    echo "PYTHON_VERSION=\"$python_version\""
    echo "PYTHON_WRAPPED=\"$python_wrapped\""
    echo "PYTHON_ENV=\"$python_env\""
}

detect_python
