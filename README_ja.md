# bw-cc-plugins

AI によるコード・文書レビューと、プロジェクト文書構造管理のための Claude Code プラグインマーケットプレイス。

[English README (README.md)](README.md)

## プラグイン一覧

| プラグイン | バージョン | 説明 |
|-----------|-----------|------|
| **kaizen** | 0.0.2 | AI によるコード・文書レビュー。段階的な対話提示と自動修正に対応 |
| **doc-structure** | 0.0.1 | `.doc_structure.yaml` によるプロジェクト文書構成の定義・クエリ |

## インストール

### 方法 A: マーケットプレイス経由（永続）

Claude Code セッション内で:

```
/plugin marketplace add BlueEventHorizon/bw-cc-plugins
/plugin install kaizen@bw-cc-plugins
/plugin install doc-structure@bw-cc-plugins
```

すでにinstall済みの場合は、ターミナルから:

```bash
claude plugin enable kaizen@bw-cc-plugins
claude plugin enable doc-structure@bw-cc-plugins
```

<img src="./images/install_kaizen.png" width="900">

`marketplace add` は GitHub リポジトリをプラグイン取得元として登録します（ユーザーごとに1回）。一度インストールすれば、常に利用可能です。

### 方法 B: ローカルディレクトリ（セッション限定）

```bash
git clone https://github.com/BlueEventHorizon/bw-cc-plugins.git
claude --plugin-dir ./bw-cc-plugins/plugins/kaizen
claude --plugin-dir ./bw-cc-plugins/plugins/doc-structure
```

> **注意**: `--plugin-dir` はセッション限定です。Claude Code を起動するたびに指定が必要です。解除するには、フラグなしで起動するだけです。

### 更新

ターミナルから:

```bash
claude plugin update kaizen@bw-cc-plugins --scope local
claude plugin update doc-structure@bw-cc-plugins --scope local
```

## kaizen

AI によるコード・文書レビュー。段階的な対話提示と自動修正に対応。

### 使い方

```
/kaizen:review <種別> [対象] [--エンジン] [--auto-fix]
```

| 引数 | 値 |
|------|-----|
| 種別 | `code` \| `requirement` \| `design` \| `plan` \| `generic` |
| 対象 | ファイルパス（複数可）、ディレクトリ、Feature 名、省略で対話的に決定 |
| エンジン | `--codex`（デフォルト）\| `--claude` |
| モード | `--auto-fix`（致命的問題を自動修正） |

### 使用例

```bash
# ディレクトリ内のソースコードをレビュー
/kaizen:review code src/

# 特定ファイルをレビュー
/kaizen:review code src/services/auth.swift

# Feature 名で要件定義書をレビュー
/kaizen:review requirement login

# 設計書をレビュー
/kaizen:review design specs/login/design/login_design.md

# 計画書をレビュー（自動修正付き）
/kaizen:review plan specs/login/plan/login_plan.md --auto-fix

# 任意の文書をレビュー
/kaizen:review generic README.md

# ブランチ差分をレビュー（対象省略 = 現在のブランチの変更）
/kaizen:review code

# Claude エンジンを使用（Codex の代わりに）
/kaizen:review code src/ --claude
```

### スキル構成

| スキル | ユーザー呼び出し | 説明 |
|--------|-----------------|------|
| `review` | 可能 | メインのレビュースキル。種別判定、参考文書収集、レビュー実行 |
| `present-staged` | AI 専用 | レビュー結果を段階的・対話的に提示 |
| `fix-staged` | AI 専用 | レビュー指摘に基づく修正を実行。参考文書を収集し（DocAdvisor Skill or .doc_structure.yaml）修正 |

### レビュー種別

| 種別 | 対象 |
|------|------|
| `code` | ソースコードファイル・ディレクトリ |
| `requirement` | 要件定義書 |
| `design` | 設計書 |
| `plan` | 開発計画書 |
| `generic` | 任意の文書（ルール、スキル定義、README 等） |

### 重大度レベル

| レベル | 意味 |
|--------|------|
| 致命的 | 修正必須。バグ、セキュリティ問題、データ損失リスク、仕様違反 |
| 品質 | 修正推奨。コーディング規約、エラーハンドリング、パフォーマンス |
| 改善 | あると良い。可読性向上、リファクタリング提案 |

### レビュー観点

プラグインにはデフォルトのレビュー観点が `defaults/review_criteria.md` に同梱されています。プロジェクト固有の観点を使用する場合は以下の優先順で解決されます:

1. **DocAdvisor**: プロジェクトに DocAdvisor Skill（`/query-rules`）がある場合、プロジェクト固有のレビュー観点を動的に取得
2. **プロジェクト設定**: `.claude/review-config.yaml` にカスタムパスを保存
3. **プラグインデフォルト**: 同梱の `defaults/review_criteria.md` にフォールバック

## doc-structure

`.doc_structure.yaml` によるプロジェクト文書構成の定義・クエリ。

### 使い方

```bash
# .doc_structure.yaml を対話的に作成・更新
/doc-structure:init-doc-structure

# 確認プロンプトなしで作成
/doc-structure:init-doc-structure --auto

# 全ての文書ディレクトリを表示
/doc-structure:where

# 特定カテゴリを表示
/doc-structure:where specs

# 特定の種別のパスを取得
/doc-structure:where specs requirement
```

### スキル構成

| スキル | ユーザー呼び出し | 説明 |
|--------|-----------------|------|
| `init-doc-structure` | 可能 | プロジェクトのディレクトリをスキャン・分類し、`.doc_structure.yaml` を生成 |
| `where` | 可能 | `.doc_structure.yaml` をクエリして文書ディレクトリのパスを返す |

### スキーマリファレンス

完全な仕様は [docs/doc_structure_format.md](docs/doc_structure_format.md) を参照してください。

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

## 動作要件

- [Claude Code](https://claude.ai/code) CLI
- [Codex CLI](https://github.com/openai/codex)（任意。Codex エンジン使用時に必要。未インストールの場合は Claude にフォールバック）

## ライセンス

[MIT](LICENSE)
