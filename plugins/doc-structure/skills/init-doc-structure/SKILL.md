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
  rules/                   → [category]: rules  [doc_type]: rule
  specs/core/requirements/ → [category]: specs  [doc_type]: requirement
  specs/core/design/       → [category]: specs  [doc_type]: design
  ...
```

### Step 4: 対話的確認

分類結果をユーザーに提示し、確認・調整を求める:

分類結果を番号付き一覧で提示する。glob パスは展開結果も表示する。

提示例:
```
分類結果:
  1. [category]: rules  [doc_type]: rule        → rules/
  2. [category]: specs  [doc_type]: requirement  → specs/*/requirements/
     - specs/login/requirements/
     - specs/auth/requirements/
     - specs/archived/requirements/ *exclude*
     - specs/_template/requirements/
  3. [category]: specs  [doc_type]: design       → specs/*/design/
     - specs/login/design/
     - specs/auth/design/
  4. [category]: specs  [doc_type]: plan         → specs/*/plan/
  5. [category]: specs  [doc_type]: reference    → specs/shared/, specs/issues/

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

### doc_type 定義（固定。全プロジェクト・全プラグインで共通）

| category | doc_type | 意味 | 含まれる文書の例 |
|----------|----------|------|-----------------|
| rules | rule | 開発プロセスのルール・規約・手順 | コーディング規約、命名規則、Git ワークフロー、レビュー手順、CI/CD ルール |
| specs | requirement | 「何を実現するか」のゴール定義 | ユーザーストーリー、機能要件、非機能要件、ビジネスルール、受入条件 |
| specs | design | 「どう構成するか」の技術的構造 | アーキテクチャ設計、DB スキーマ設計、画面設計、シーケンス図、状態遷移図 |
| specs | plan | 「どの順で作るか」の作業計画 | タスク分割、実装順序、マイルストーン、スプリント計画、移行計画 |
| specs | api | 外部インターフェースの契約 | REST エンドポイント定義、リクエスト/レスポンス仕様、OpenAPI/Swagger、GraphQL スキーマ |
| specs | reference | 判断の根拠となる補助文書 | 技術調査メモ、比較検討資料、外部仕様の要約、議事録、用語集 |
| specs | spec | 上記に該当しない仕様文書（デフォルト） | 分類不明な仕様文書の一時的な受け皿 |
