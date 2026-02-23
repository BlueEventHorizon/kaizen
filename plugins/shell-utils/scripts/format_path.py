#!/usr/bin/env python3
"""format_path.py - Format file paths for readable terminal display.

Created by k_terada

Features:
    1. $HOME -> ~ replacement
    2. CWD-relative path (if shorter)
    3. Middle truncation for long paths (--truncate N)
    4. Git root-relative display (--git-root)

Usage:
    python3 format_path.py PATH [PATH ...]
    python3 format_path.py --truncate 40 PATH [PATH ...]
    python3 format_path.py --git-root PATH [PATH ...]
    python3 format_path.py --shell-func
"""

import os
import sys
import subprocess


def get_home_dir():
    """Get home directory path."""
    return os.path.expanduser("~")


def get_git_root(path):
    """Get the git repository root for the given path."""
    check_dir = path if os.path.isdir(path) else os.path.dirname(path)
    if not check_dir:
        check_dir = "."
    try:
        result = subprocess.run(
            ["git", "-C", check_dir, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def replace_home(path, home=None):
    """Replace home directory prefix with ~."""
    if home is None:
        home = get_home_dir()
    if path == home:
        return "~"
    if path.startswith(home + "/"):
        return "~" + path[len(home):]
    return path


def to_relative(path, cwd=None):
    """Convert to CWD-relative path if shorter and not too deep."""
    if cwd is None:
        cwd = os.getcwd()
    try:
        rel = os.path.relpath(path, cwd)
    except ValueError:
        # Different drives on Windows
        return None
    # Reject if traversal is too deep (3+ levels up)
    if rel.startswith("../../.."):
        return None
    return rel


def truncate_middle(path, max_len):
    """Truncate middle of path if it exceeds max_len.

    Example: ~/data/dev/…/apps/CCMonitor
    """
    if len(path) <= max_len:
        return path

    # Split into parts
    parts = path.split("/")
    if len(parts) <= 3:
        return path

    # Keep first part and last 2 parts, collapse middle
    head = parts[0]
    tail = "/".join(parts[-2:])
    ellipsis = "\u2026"  # …

    # Try removing middle parts until it fits
    for i in range(1, len(parts) - 2):
        candidate = head + "/" + ellipsis + "/" + "/".join(parts[-(len(parts) - 1 - i):])
        if len(candidate) <= max_len:
            return candidate

    # Minimum: head/…/last_two
    return head + "/" + ellipsis + "/" + tail


def to_git_relative(path):
    """Format path relative to git root with repo name prefix.

    Example: <CCMonitor>/src/main.py
    """
    git_root = get_git_root(path)
    if git_root is None:
        return None
    repo_name = os.path.basename(git_root)
    abs_path = os.path.abspath(path)
    if abs_path == git_root:
        return f"<{repo_name}>"
    if abs_path.startswith(git_root + "/"):
        rel = abs_path[len(git_root) + 1:]
        return f"<{repo_name}>/{rel}"
    return None


def format_path(path, truncate=0, git_root=False):
    """Format a single path for display.

    Returns the shortest readable representation.
    """
    abs_path = os.path.abspath(os.path.expanduser(path))
    home = get_home_dir()

    if git_root:
        result = to_git_relative(abs_path)
        if result:
            if truncate > 0:
                return truncate_middle(result, truncate)
            return result

    # Candidates: home-replaced and relative
    home_replaced = replace_home(abs_path, home)
    relative = to_relative(abs_path)

    # Pick the shorter one
    if relative and len(relative) < len(home_replaced):
        result = relative
    else:
        result = home_replaced

    if truncate > 0:
        result = truncate_middle(result, truncate)

    return result


def print_shell_func():
    """Output a shell function definition that can be eval'd."""
    print("""# Shell function for path display formatting
# Usage: eval "$(python3 format_path.py --shell-func)"
#        display_path "/some/long/path"
display_path() {
    local abs_path="$1"
    local home_replaced="${abs_path/#$HOME/~}"
    printf '%s' "$home_replaced"
}""")


def main():
    args = sys.argv[1:]

    if not args:
        print(f"Usage: {sys.argv[0]} [--truncate N] [--git-root] [--shell-func] PATH [PATH ...]",
              file=sys.stderr)
        sys.exit(1)

    # Parse options
    truncate = 0
    git_root = False
    paths = []

    i = 0
    while i < len(args):
        if args[i] == "--shell-func":
            print_shell_func()
            return
        elif args[i] == "--truncate" and i + 1 < len(args):
            try:
                truncate = int(args[i + 1])
            except ValueError:
                print(f"Error: --truncate requires an integer, got '{args[i + 1]}'",
                      file=sys.stderr)
                sys.exit(1)
            i += 2
            continue
        elif args[i] == "--git-root":
            git_root = True
        else:
            paths.append(args[i])
        i += 1

    if not paths:
        print("Error: No paths specified", file=sys.stderr)
        sys.exit(1)

    for p in paths:
        print(format_path(p, truncate=truncate, git_root=git_root))


if __name__ == "__main__":
    main()
