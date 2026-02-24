# bw-cc-plugins

A Claude Code plugin marketplace for AI-powered code & document review, and project document structure management.

[Japanese README (README_ja.md)](README_ja.md)

## Plugins

| Plugin | Version | Description |
|--------|---------|-------------|
| **kaizen** | 0.0.3 | AI-powered code & document review with staged presentation and auto-fix |
| **doc-structure** | 0.0.4 | Define and query project document structure (`.doc_structure.yaml`) |
| **shell-utils** | 0.0.1 | Shell utility collection: Python environment detection, path formatting |

## Installation

### Option A: Marketplace (persistent)

Inside a Claude Code session:

```
/plugin marketplace add BlueEventHorizon/bw-cc-plugins
/plugin install kaizen@bw-cc-plugins
/plugin install doc-structure@bw-cc-plugins
/plugin install shell-utils@bw-cc-plugins
```

If you already installed, from your terminal:

```bash
claude plugin enable kaizen@bw-cc-plugins
claude plugin enable doc-structure@bw-cc-plugins
claude plugin enable shell-utils@bw-cc-plugins
```

<img src="./images/install_kaizen.png" width="900">

`marketplace add` registers the GitHub repo as a plugin source (once per user). Once installed, the plugin is always available.

### Option B: Local directory (per session)

```bash
git clone https://github.com/BlueEventHorizon/bw-cc-plugins.git
claude --plugin-dir ./bw-cc-plugins/plugins/kaizen
claude --plugin-dir ./bw-cc-plugins/plugins/doc-structure
claude --plugin-dir ./bw-cc-plugins/plugins/shell-utils
```

> **Note**: `--plugin-dir` is session-only. You must specify it every time you start Claude Code. To unload, simply start without the flag.

### Update

From your terminal:

```bash
claude plugin update kaizen@bw-cc-plugins --scope local
claude plugin update doc-structure@bw-cc-plugins --scope local
claude plugin update shell-utils@bw-cc-plugins --scope local
```

## kaizen

AI-powered code & document review with staged presentation and auto-fix.

### Usage

```
/kaizen:review <type> [target] [--engine] [--auto-fix]
```

| Argument | Values |
|----------|--------|
| type | `code` \| `requirement` \| `design` \| `plan` \| `generic` |
| target | File path(s), directory, feature name, or omit for interactive |
| engine | `--codex` (default) \| `--claude` |
| mode | `--auto-fix` (auto-fix critical issues) |

### Examples

```bash
# Review source files in a directory
/kaizen:review code src/

# Review a specific file
/kaizen:review code src/services/auth.swift

# Review requirements by feature name
/kaizen:review requirement login

# Review a design document
/kaizen:review design specs/login/design/login_design.md

# Review a plan with auto-fix
/kaizen:review plan specs/login/plan/login_plan.md --auto-fix

# Review any document
/kaizen:review generic README.md

# Review branch diff (no target = current branch changes)
/kaizen:review code

# Use Claude engine instead of Codex
/kaizen:review code src/ --claude
```

### Skills

| Skill | User-invocable | Description |
|-------|---------------|-------------|
| `review` | Yes | Main review skill. Detects review type, collects references, and executes review |
| `present-staged` | No (AI only) | Presents review findings interactively, one item at a time |
| `fix-staged` | No (AI only) | Fixes issues based on review findings with reference doc collection (DocAdvisor or .doc_structure.yaml) |

### Review Types

| Type | Target |
|------|--------|
| `code` | Source code files and directories |
| `requirement` | Requirements documents |
| `design` | Design documents |
| `plan` | Development plans |
| `generic` | Any document (rules, skills, READMEs, etc.) |

### Severity Levels

| Level | Meaning |
|-------|---------|
| Critical | Must fix. Bugs, security issues, data loss risks, spec violations |
| Major | Should fix. Coding standards, error handling, performance |
| Minor | Nice to have. Readability, refactoring suggestions |

### Review Criteria

The plugin includes default review criteria in `defaults/review_criteria.md`. Projects can override this by:

1. **DocAdvisor**: If the project has DocAdvisor skills (`/query-rules`), the plugin queries them for project-specific review criteria
2. **Project config**: Save a custom path in `.claude/review-config.yaml`
3. **Plugin default**: Falls back to the bundled `defaults/review_criteria.md`

## doc-structure

Define and query project document structure using `.doc_structure.yaml`.

### Usage

```bash
# Create or update .doc_structure.yaml interactively
/doc-structure:init-doc-structure

# Create without confirmation prompts
/doc-structure:init-doc-structure --auto

# Query all document locations
/doc-structure:where

# Query a specific category
/doc-structure:where specs

# Query a specific doc type
/doc-structure:where specs requirement
```

### Skills

| Skill | User-invocable | Description |
|-------|---------------|-------------|
| `init-doc-structure` | Yes | Scans project directories, classifies them as rules/specs, and generates `.doc_structure.yaml` |
| `where` | Yes | Queries `.doc_structure.yaml` to return document directory paths |

### Schema Reference

See [docs/doc_structure_format.md](docs/doc_structure_format.md) for the full specification.

```yaml
version: "1.0"

specs:
  requirement:
    paths: [specs/requirements/]
  design:
    paths: [specs/design/]

rules:
  rule:
    paths: [rules/]
```

## shell-utils

Shell utility collection for Claude Code projects. Python environment detection and path formatting.

### Usage

```bash
# Detect Python environment
/shell-utils:detect-python

# Format paths for display
/shell-utils:format-path /Users/name/long/path/to/project

# Format with middle truncation
/shell-utils:format-path --truncate 30 /Users/name/long/path/to/project

# Format relative to git root
/shell-utils:format-path --git-root /repo/deep/nested/file.py
```

### Skills

| Skill | User-invocable | Description |
|-------|---------------|-------------|
| `detect-python` | Yes | Detect usable Python3 command, bypassing Claude Code shell-snapshots wrapper. Detects pyenv/venv/conda |
| `format-path` | Yes | Format file paths for readable display: `$HOME` → `~`, CWD-relative, middle truncation, git-root relative |

### Path Formatting Features

| Feature | Example |
|---------|---------|
| `$HOME` → `~` | `/Users/name/dev/proj` → `~/dev/proj` |
| CWD-relative (if shorter) | `../sibling/file` |
| Middle truncation | `~/data/dev/…/apps/MyProject` |
| Git root-relative | `<MyProject>/src/main.py` |

### Script Usage from Other Plugins

```bash
# Detect Python (outputs eval-able variables)
eval "$(bash ${CLAUDE_PLUGIN_ROOT}/scripts/detect_python.sh)"

# Use detected Python to run scripts
$PYTHON_CMD ${CLAUDE_PLUGIN_ROOT}/scripts/format_path.py /some/path

# Output shell function for embedding
$PYTHON_CMD ${CLAUDE_PLUGIN_ROOT}/scripts/format_path.py --shell-func
```

## Requirements

- [Claude Code](https://claude.ai/code) CLI
- Python 3 (for shell-utils)
- [Codex CLI](https://github.com/openai/codex) (optional, for Codex engine; falls back to Claude if unavailable)

## License

[MIT](LICENSE)
