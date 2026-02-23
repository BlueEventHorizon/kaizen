# .doc_structure.yaml Format Specification

> Version: 1.0 | Created by: k_terada

## Purpose

`.doc_structure.yaml` is a project-level convention that declares where different types of documents live.
It serves as a single source of truth for document organization, consumed by multiple tools:

- **Skills** (e.g., `/start-planning`, `/start-requirements`) — know where to create documents
- **Doc Advisor** — derives `root_dirs` and `doc_type` for ToC generation
- **Review tools** (e.g., kaizen) — determine document type for review criteria selection
- **Scripts** — parse YAML directly for programmatic access

## File Location

Place `.doc_structure.yaml` at the **project root** (same level as `.git/`).

## Schema

```yaml
# .doc_structure.yaml
version: "1.0"

specs:
  <doc_type>:
    paths: [<directory_path>, ...]
    exclude: ["<dir_name>", ...]        # optional
    description: "<optional description>"

rules:
  <doc_type>:
    paths: [<directory_path>, ...]
    exclude: ["<dir_name>", ...]        # optional
    description: "<optional description>"
```

### Fields

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `version` | Yes | string | Schema version. Currently `"1.0"` |
| `specs` | No | object | Specification document types (requirements, designs, plans, etc.) |
| `rules` | No | object | Rule document types (development rules, workflows, guidelines, etc.) |

### Doc Type Entry

Each key under `specs` or `rules` is a **doc_type name** (e.g., `requirement`, `design`, `plan`).

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `paths` | Yes | array[string] | Directory paths (relative to project root). Glob patterns (`*`) supported |
| `exclude` | No | array[string] | Directory names to exclude. Matches any path component with that name |
| `description` | No | string | Human-readable description of this document type |

### Path Format

- Paths are relative to the project root
- Trailing `/` is optional but recommended for clarity
- Glob pattern `*` matches any single directory level

```yaml
# Literal path
paths: [specs/requirements/]

# Glob pattern (matches specs/main/requirements/, specs/auth/requirements/, etc.)
paths: ["specs/*/requirements/"]

# Multiple paths
paths:
  - specs/requirements/
  - other_specs/requirements/
```

### Exclude Format

- Each entry is a **directory name** (not a full path)
- If any component of a resolved path matches an exclude name, that path is excluded
- Useful for filtering glob pattern (`*`) expansion results

```yaml
# Exclude directories named "archived" or "_template" anywhere in matched paths
exclude: ["archived", "_template"]

# specs/login/requirements/     → included
# specs/archived/requirements/  → EXCLUDED (contains "archived")
# specs/_template/requirements/ → EXCLUDED (contains "_template")
```

## Recommended Doc Type Names

These names are recommended for interoperability. Custom names are also valid.

### For `specs` category

| Name | Description |
|------|-------------|
| `requirement` | Functional and non-functional requirements |
| `design` | Technical design documents, architecture specs |
| `plan` | Implementation plans, roadmaps, task breakdowns |
| `api` | API specifications, endpoint documentation |
| `reference` | Reference materials, data dictionaries |

### For `rules` category

| Name | Description |
|------|-------------|
| `rule` | Development rules, coding standards, conventions |
| `workflow` | Workflow procedures, process guides |
| `guide` | Best practices, how-to guides |

## Examples

### Flat Structure

```yaml
version: "1.0"

specs:
  requirement:
    paths: [specs/requirements/]
    description: "Functional and non-functional requirements"
  design:
    paths: [specs/design/]
    description: "Technical design documents"
  plan:
    paths: [specs/plan/]

rules:
  rule:
    paths: [rules/]
```

### Feature-Based Structure

```yaml
version: "1.0"

specs:
  requirement:
    paths: ["specs/*/requirements/"]
  design:
    paths: ["specs/*/design/"]
  plan:
    paths: ["specs/*/plan/"]

rules:
  rule:
    paths: [rules/]
  workflow:
    paths: [rules/workflow/]
```

### Feature-Based Structure (with exclude)

```yaml
version: "1.0"

specs:
  requirement:
    paths: ["specs/*/requirements/"]
    exclude: ["archived", "_template"]
  design:
    paths: ["specs/*/design/"]
    exclude: ["archived"]

rules:
  rule:
    paths: [rules/]
```

### Mixed Structure

```yaml
version: "1.0"

specs:
  requirement:
    paths:
      - specs/requirements/
      - modules/*/requirements/
  design:
    paths: [specs/design/]

rules:
  rule:
    paths: [rules/]
```

### Minimal

```yaml
version: "1.0"

specs:
  spec:
    paths: [docs/specs/]

rules:
  rule:
    paths: [docs/rules/]
```

## Consumer Guide

### For Skills (via `/doc-structure:where`)

Skills can query document locations without parsing YAML:

```
/doc-structure:where specs requirement
→ specs/requirements/

/doc-structure:where specs plan
→ specs/plan/

/doc-structure:where
→ (shows all categories and paths)

/doc-structure:where --resolve
→ (all paths with globs expanded and excludes applied)
```

### For Scripts (direct YAML parsing)

```python
import yaml

with open(".doc_structure.yaml") as f:
    structure = yaml.safe_load(f)

# Get paths for a specific doc_type
plan_paths = structure["specs"]["plan"]["paths"]
# → ["specs/plan/"]

# Collect all root_dirs for a category
specs_dirs = []
for doc_type_info in structure.get("specs", {}).values():
    specs_dirs.extend(doc_type_info.get("paths", []))
# → ["specs/requirements/", "specs/design/", "specs/plan/"]
```

### For Doc Advisor

Doc Advisor can derive its `config.yaml` settings from `.doc_structure.yaml`:

```
.doc_structure.yaml specs.*.paths  →  config.yaml specs.root_dirs
.doc_structure.yaml rules.*.paths  →  config.yaml rules.root_dirs
doc_type keys                      →  ToC entry doc_type field
```

## Versioning

- The `version` field uses semantic versioning (`"major.minor"`)
- Minor version changes are backward-compatible (new optional fields)
- Major version changes may break consumers
- Consumers should check `version` and warn on unsupported major versions
