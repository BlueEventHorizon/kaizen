---
name: where
description: |
  Query .doc_structure.yaml to find where documents of a specific type are located.
  Returns directory paths for the requested category and doc_type.
  Designed to be called by other skills to avoid YAML parsing.
  Trigger: "where are the requirements", "where do plans go", "document paths"
user-invocable: true
argument-hint: "[--resolve | <category> [<doc_type>]]"
---

# /doc-structure:where

## Overview

Query `.doc_structure.yaml` to return document directory paths.
Other skills can call this instead of parsing YAML directly.

## EXECUTION RULES
- Exit plan mode if active. Do NOT ask for confirmation about plan mode.
- If `.doc_structure.yaml` does not exist, report error and suggest running `/doc-structure:init-doc-structure`.

## Input

**Arguments**: `$ARGUMENTS`

| Format | Meaning | Example |
|--------|---------|---------|
| (empty) | Show all categories and paths | `/doc-structure:where` |
| `<category>` | Show all doc_types in category | `/doc-structure:where specs` |
| `<category> <doc_type>` | Show paths for specific type | `/doc-structure:where specs requirement` |
| `--resolve` | Full resolved list (globs expanded, excludes applied) | `/doc-structure:where --resolve` |

## Procedure

### Step 1: Read .doc_structure.yaml

Read `.doc_structure.yaml` from the project root.

If the file does not exist:
```
Error: .doc_structure.yaml not found.
Run /doc-structure:init-doc-structure to create it.
```

### Step 2: 引数解析 [MANDATORY]

`$ARGUMENTS` を以下の優先順位で解析する:

1. `--resolve` を検索（単語単位）
   - 見つかった場合 → Step 5（フルリゾルブモード）へ。他の引数は無視。
2. 残りを空白で分割:
   - `word[0]` → `<category>` (`specs` | `rules`)
   - `word[1]` → `<doc_type>` (例: `requirement`, `design`, `rule`)
   - 両方なし → 全カテゴリ表示（Step 3 の「No arguments」）
3. エラー:
   - 不明な category → `"Unknown category: <value>. Available: specs, rules"`
   - 不明な doc_type → `"Unknown doc_type '<value>' in <category>. Available: <list>"`

### Step 3: 応答

#### No arguments — show all

```
specs:
  requirement: specs/requirements/
  design: specs/design/
  plan: specs/plan/
rules:
  rule: rules/
```

#### Category only — show doc_types in category

```
/doc-structure:where specs
→
specs:
  requirement: specs/requirements/
  design: specs/design/
  plan: specs/plan/
```

#### Category + doc_type — show paths

```
/doc-structure:where specs requirement
→ specs/requirements/
```

If a doc_type has `exclude`, show it:
```
/doc-structure:where specs requirement
→ specs/*/requirements/
  exclude: archived, _template
```

If a doc_type has multiple paths:
```
/doc-structure:where specs requirement
→ specs/requirements/
  modules/auth/requirements/
```

### Step 4: Glob expansion (if applicable)

If a path contains `*` (glob pattern), expand it to show actual matching directories,
**excluding directories that match the `exclude` list**:

```
/doc-structure:where specs requirement
→ Pattern: specs/*/requirements/
  Exclude: archived, _template
  Matches:
    specs/main/requirements/
    specs/auth/requirements/
    specs/csv_import/requirements/
```

Use `ls -d` or equivalent to expand glob patterns.
Apply exclude filter: remove paths where any component matches an exclude name.

### Step 5: Full resolve mode (--resolve)

When `--resolve` is specified, return the complete resolved structure:
all categories, all doc_types, all paths expanded with excludes applied.

```
/doc-structure:where --resolve
→
specs:
  requirement:
    - specs/login/requirements/
    - specs/auth/requirements/
  design:
    - specs/login/design/
    - specs/auth/design/
  plan:
    - specs/login/plan/
    - specs/auth/plan/
rules:
  rule:
    - rules/
```

Procedure:
1. Read `.doc_structure.yaml`
2. For each category and doc_type:
   a. If paths contain `*`, expand with `ls -d` or equivalent
   b. Apply `exclude` filter: remove paths where any component matches an exclude name
   c. List remaining resolved paths
3. Output in the structured format above

This mode is designed for other skills (e.g., kaizen) to get all document paths
without reading `.doc_structure.yaml` directly.

## Output Format

Keep output minimal and machine-friendly. No extra decoration.
The calling skill or user should get paths they can directly use.
