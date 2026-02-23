---
name: init-doc-structure
description: |
  Create or update .doc_structure.yaml for the current project.
  Scans directories for markdown files, then AI classifies them as rules/specs with doc_type interactively.
  Trigger: "init doc structure", "create doc structure", "setup document structure"
user-invocable: true
argument-hint: ""
---

# /doc-structure:init-doc-structure

## Overview

対話的に `.doc_structure.yaml` をプロジェクトルートに作成・更新する。
このファイルはドキュメントの所在を宣言し、他のツール（Doc Advisor, kaizen 等）がドキュメントを参照できるようにする。

## EXECUTION RULES
- Exit plan mode if active. Do NOT ask for confirmation about plan mode.
- If `.doc_structure.yaml` already exists, switch to **review mode** (show current, suggest changes).

## Procedure

### Step 1: 既存ファイルの確認

`.doc_structure.yaml` がプロジェクトルートに存在するか確認する。

- **存在する** → 現在の内容を表示し、更新するか再生成するかユーザーに確認。
- **存在しない** → Step 2 へ。

### Step 2: ディレクトリスキャン

スクリプトのディレクトリを特定する:
- プラグインとして実行中: プラグインの `scripts/` ディレクトリを使用
- フォールバック: `classify_dirs.py` を一般的な場所から検索

```bash
python3 <scripts_dir>/classify_dirs.py
```

スキャン結果（JSON）を取得する。`readme_only: true` のディレクトリは分類対象外としてスキップする。

### Step 3: AI による分類判定 [MANDATORY]

同ディレクトリの `classification_rules.md` を Read し、そのルールに従ってスキャン結果の各ディレクトリに category と doc_type を割り当てる。

**進捗表示 [MANDATORY]**: 各ディレクトリの判定ごとに結果をユーザーに表示すること。
```
分類中...
  rules/ → rules / rule
  specs/core/requirements/ → specs / requirement
  specs/core/design/ → specs / design
  ...
```

### Step 4: 対話的確認

分類結果をユーザーに提示し、確認・調整を求める:

分類結果を番号付き一覧で提示する。glob パスは展開結果も表示する。

提示例:
```
分類結果:
  1. rules / rule       → rules/
  2. specs / requirement → specs/*/requirements/
     - specs/login/requirements/
     - specs/auth/requirements/
     - specs/archived/requirements/ *exclude*
     - specs/_template/requirements/
  3. specs / design      → specs/*/design/
     - specs/login/design/
     - specs/auth/design/
  4. specs / plan        → specs/*/plan/
  5. specs / reference   → specs/shared/, specs/issues/

修正・除外したいものはありますか？（例: "archived除外", "5をspecに変更"）
```

- ディレクトリ名（例: "archived除外"）→ 該当する glob パスの `exclude` に追加
- 分類番号（例: "5をspecに変更"）→ category や doc_type を修正
- 問題なければそのまま次へ進む

### Step 5: .doc_structure.yaml の生成

確定した分類結果から `.doc_structure.yaml` を生成し、プロジェクトルートに書き出す。

### Step 6: 結果表示

生成したファイルの内容を表示し、次のステップを案内する:

```
.doc_structure.yaml created successfully.

Next steps:
- Other skills can query document locations: /doc-structure:where specs requirement
- If using Doc Advisor: run /classify-docs to sync config.yaml
- Commit .doc_structure.yaml to version control
```

---

## Schema Reference

See: https://github.com/BlueEventHorizon/bw-cc-plugins/blob/main/docs/doc_structure_format.md

### Quick reference

```yaml
version: "1.0"

specs:
  <doc_type>:
    paths: [<dir_path>, ...]
    exclude: ["<dir_name>", ...]  # optional, directory name match
    description: "<optional>"     # optional

rules:
  <doc_type>:
    paths: [<dir_path>, ...]
    exclude: ["<dir_name>", ...]  # optional
```

### 推奨 doc_type 名

| Category | Name | Description |
|----------|------|-------------|
| specs | requirement | 要件定義書 |
| specs | design | 設計書 |
| specs | plan | 実装計画書 |
| specs | api | API 仕様書 |
| specs | reference | 参考資料 |
| rules | rule | 開発ルール・規約・標準・ワークフロー・ガイド |
