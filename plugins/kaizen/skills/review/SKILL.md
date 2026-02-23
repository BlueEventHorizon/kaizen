---
name: review
description: |
  レビュー実行。コード、要件定義書、設計書、計画書、汎用文書に対応。
  Codex / Claude Code の2エンジンから選択可能（デフォルト: Codex）。
  段階的・対話的にレビュー結果を提示。
  トリガー: "レビュー", "review", "レビューして", "/review"
---

# /review Skill

レビューを実行する。種別（requirement / design / code / plan）とエンジン（Codex / Claude）を組み合わせて使用。

## コマンド構文

```
/review <種別> [対象] [--エンジン] [--auto-fix]

種別: requirement | design | code | plan | generic
対象: ファイルパス(複数可) | Feature名 | ディレクトリ | 省略(=対話で決定)
エンジン: --codex(デフォルト) | --claude
モード: --auto-fix（自動修正モード）
```

### 使用例

```bash
/review code src/                                       # ディレクトリ内のソースコード
/review code src/services/auth.swift                    # 特定ファイル
/review requirement login                               # Feature 名で要件定義書
/review design specs/login/design/login_design.md       # 設計書
/review code src/ --claude                              # Claude エンジンを使用
/review code                                            # ブランチ差分のコード
/review plan specs/login/plan/login_plan.md --auto-fix  # 自動修正モード
/review generic README.md                               # 任意の文書
/review generic docs/CONTRIBUTING.md docs/README.md     # 複数ファイル
```

---

## ワークフロー

### Phase 1: 引数解析と環境確認

1. `$ARGUMENTS` を解析:
   - 最初の単語 → 種別（`requirement` | `design` | `code` | `plan` | `generic`）
   - `--codex` または `--claude` → エンジン指定
   - `--auto-fix` → 自動修正モード
   - 残り → 対象（ファイルパス(複数可) / Feature名 / ディレクトリ）
     - スペース区切りで複数のファイルパスを指定可能

2. **パラメータ補完**（引数が不完全な場合）:

   種別または対象が未指定の場合、以下の順で補完を試みる:

   a. **resolve_review_context.py の結果を利用**（Phase 1.5）
      - スクリプトが種別を判定できた場合、その結果を推奨として使用

   b. **会話コンテキストからの推論**（スクリプトで解決できない場合）
      - 直前に作成・編集・議論していたファイルから種別と対象を推定
      - 例: SKILL.md を編集中 → generic + そのファイルパスを推定
      - 例: 要件定義書を作成直後 → requirement + 作成ファイルを推定

   c. **推奨の提示**（推論できた場合、ユーザー確認必須）
      推論結果は確定ではなく**推奨**として提示し、ユーザーの承認を得る:
      ```
      以下の設定でレビューを実行します:
      - 種別: generic
      - 対象: docs/CONTRIBUTING.md, docs/README.md
      - エンジン: Codex
      → はい / 変更する
      ```

   d. **推論不可の場合** → ユーザーに確認（現状通り）

3. **エンジン確認**:
   - `--claude` 指定 → Claude を使用
   - `--codex` 指定、または省略 → `which codex` を実行
     - 存在する → Codex を使用
     - 存在しない → Claude にフォールバック、「Codex が見つからないため Claude で実行します」と通知

4. **環境確認**（順に実行し、利用可能な機能セットを決定）:
   ```
   1. which codex → エンジン決定
   2. .doc_structure.yaml の存在確認
      - なければ /doc-structure:init-doc-structure を起動し作成を促す
      - 作成されなければエラー終了
   3. レビュー観点定義の探索（後述「レビュー観点の探索」参照）
   4. 不足があればユーザーに通知（何が使えて何が使えないか）
   ```

#### レビュー観点の探索 [MANDATORY]

以下の優先順で検索し、最初に見つかったものを `{review_criteria_path}` として以降のフェーズで使用する:

1. **`/query-rules` Skill**（DocAdvisor）に「レビュー観点の文書」を問い合わせ → パスを動的に特定
   - 利用可否: `.claude/skills/query-rules/SKILL.md` の存在で判断（利用不可ならスキップ）
2. **`.claude/review-config.yaml`** に保存済みのパスがあれば使用
3. **`${CLAUDE_PLUGIN_ROOT}/defaults/review_criteria.md`**（プラグイン同梱のデフォルト）

初回利用時に 1 も 2 も見つからない場合、ユーザーに「プロジェクトにレビュー観点の文書はありますか？」と確認:
- パスを指定 → `.claude/review-config.yaml` に保存し、次回以降は 2 で解決
- なし → 3（プラグインのデフォルト）を使用

---

### Phase 1.5: レビュー対象の特定

検出スクリプトを実行して、種別・対象ファイル・参考文書を特定する。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/scripts/resolve_review_context.py [対象1] [対象2] ...
```

スクリプトは以下を自動判定する:
- `.doc_structure.yaml` を読み込み、パス定義から種別・Feature を検出
- `.doc_structure.yaml` がなければ `error` ステータスを返す
- コードファイルは拡張子で判定

#### スクリプト出力の処理

```json
{
  "status": "resolved | needs_input | error",
  "has_doc_structure": true,
  "type": "requirement | design | code | plan | generic | null",
  "target_files": ["path1", ...],
  "features": ["feature1", ...],
  "questions": [{"key": "type|feature|target", "message": "...", "options": [...]}],
  "error": "エラーメッセージ（status=error 時のみ）"
}
```

- `status: "resolved"` → Phase 2 へ進む
- `status: "needs_input"` → `questions` の内容をユーザーに提示し、回答を得てから再実行
- `status: "error"` → 通常は Phase 1 step 2 で解決済み。タイミング問題等で発生した場合は `/doc-structure:init-doc-structure` を起動し `.doc_structure.yaml` の作成を促す。作成後にスクリプトを再実行

#### code で対象未指定の場合

スクリプトで解決できない場合、以下をユーザーに確認:
- ブランチ差分を使用するか
- ディレクトリを指定するか

---

### Phase 2: 参考文書収集

レビュー実行に必要な参考文書（ルール、関連仕様）を収集する。

#### generic 種別の場合

`/query-rules` / `/query-specs` は**使用しない**。

参考文書は最小限:
- `{review_criteria_path}` の「5. 汎用文書レビュー観点」

レビュアー（Codex / Claude subagent）が自発的に関連文書を探索することを期待する。
対象ファイルと review_criteria のみをプロンプトに含める。

#### DocAdvisor Skill を試行

`.claude/skills/query-rules/SKILL.md` が存在するか確認する。存在すれば DocAdvisor が利用可能と判断し、以下の Skill を呼び出す:

- `/query-rules` Skill → レビュー種別に関連するルール文書を特定
- `/query-specs` Skill → 関連する要件定義書・設計書を特定（存在する場合）
- `{review_criteria_path}` の該当セクション参照

DocAdvisor が利用不可（`.claude/skills/query-rules/SKILL.md` が存在しない等）の場合、以下のフォールバックに移行する。

#### DocAdvisor 利用不可時のフォールバック

`/doc-structure:where --resolve` を呼び出して全パス（glob 展開＋exclude 適用済み）を取得し、参考文書を収集する:

- `{review_criteria_path}` を参照
- `where --resolve` の `rules` カテゴリのパスから rules 文書を Glob 探索
  - 例: `rules/` → `rules/**/*.md` を探索
- `where --resolve` の `specs` カテゴリから、レビュー種別に関連する仕様書を Glob 探索
  - 例: requirement レビュー時に design のパスから関連設計書を探索
- 見つからないファイルはスキップ（エラーにしない）

> **注**: `where --resolve` が exclude 適用済みのパスを返すため、consumer 側で exclude を考慮する必要はない。

---

### Phase 3: レビュー実行（エンジン別）

#### 種別と review_criteria.md の観点セクション対応

| 種別 | review_criteria.md のセクション |
|------|-------------------------------|
| `requirement` | 「1. 要件定義書レビュー観点」 |
| `design` | 「2. 設計書レビュー観点」 |
| `plan` | 「3. 計画書レビュー観点」 |
| `code` | 「4. コードレビュー観点」 |
| `generic` | 「5. 汎用文書レビュー観点」（なければフォールバック観点を使用） |

#### 3.1 レビュー実行

##### Codex の場合

```bash
codex exec --full-auto --sandbox read-only --cd <project_dir> "<prompt>"
```

プロンプト構成:

```
以下をレビューしてください。

## レビュー対象
<対象ファイルパス>

## レビュー種別
<要件定義書 / 設計書 / 計画書 / コード / 汎用文書レビュー（generic）>

## 参考文書（必ず読んでからレビュー）
- {review_criteria_path} の「{観点セクション名}」
- <Phase 2で収集したファイルパス>

## 追加指示（generic 種別の場合のみ付加）
- 対象ファイルが参照するファイルパス・コマンド構文が実際に有効か検証すること
- 必要に応じて関連ファイルを自発的に探索し、整合性を確認すること

## 出力形式
### 🔴致命的問題
1. **[問題名]**: [説明]
   - 箇所: [ファイル:行]
   - 修正案: [具体的な修正]

### 🟡品質問題
1. **[問題名]**: [説明]
   - 箇所: [ファイル:行]

### 🟢改善提案
1. **[提案名]**: [説明]

### サマリー
- 🔴致命的: X件
- 🟡品質: X件
- 🟢改善: X件

確認や質問は不要です。具体的な指摘と修正案を出力してください。
```

**フォールバック観点**（review_criteria にセクション5がない場合、プロンプトに埋め込む）:

```
🔴致命的: 事実の誤り、論理矛盾、参照切れ、必須情報の欠落
🟡品質: 構成の一貫性、用語の不統一、責務の曖昧さ、記述の重複
🟢改善: 表現の明確化、構成改善、不足情報の補完
```

##### Claude の場合

```
subagent_type: general-purpose
prompt: |
  以下をレビューしてください。

  ## レビュー対象
  [対象ファイルパス]

  ## レビュー種別
  [要件定義書 / 設計書 / 計画書 / コード / 汎用文書レビュー（generic）]

  ## 参考文書（必ず読んでからレビュー）
  - {review_criteria_path} の「{観点セクション名}」
  - [Phase 2で収集したファイルパス]

  ## 追加指示（generic 種別の場合のみ付加）
  - 対象ファイルが参照するファイルパス・コマンド構文が実際に有効か検証すること
  - 必要に応じて関連ファイルを自発的に探索し、整合性を確認すること

  ## 出力形式
  ### 🔴致命的問題
  1. **[問題名]**: [説明]
     - 箇所: [ファイル:行]
     - 修正案: [具体的な修正]

  ### 🟡品質問題
  1. **[問題名]**: [説明]
     - 箇所: [ファイル:行]

  ### 🟢改善提案
  1. **[提案名]**: [説明]

  ### サマリー
  - 🔴致命的: X件
  - 🟡品質: X件
  - 🟢改善: X件
```

#### 3.2 自動修正（--auto-fix 時のみ）

3.1 のレビュー結果に🔴致命的問題がある場合、以下を実行する。

##### Step 1: 修正実行

`/kaizen:fix-staged --batch` を呼び出し、🔴問題を修正:

- 指摘事項: 3.1 のレビュー結果から🔴致命的問題を抽出（🟡🟢は含めない）
- 対象ファイル: target_files
- レビュー種別: review_type

fix-staged が参考文書を収集し（DocAdvisor Skill または `.doc_structure.yaml` パスで Glob）、general-purpose subagent に修正を委譲する。

##### Step 2: 再レビュー

修正後、3.1 と同じエンジン・プロンプトで再レビューを実施。🔴が0件であることを確認する。

##### 再試行上限

修正→再レビューのサイクルは**最大2回**。2回で🔴が0件にならない場合は、残存する🔴を含めて Phase 4 に結果を渡す。

#### 3.3 レビュー結果の保存（対話的モード時）

`--auto-fix` でない場合、エンジン出力を temp ファイルに保存する:

1. YAML frontmatter を付加（review_type, engine, target_files, reference_docs, timestamp）
2. エンジン出力の Markdown を本体として結合
3. `.claude/.temp/review-result-{YYYYMMDD-HHmmss}.md` に保存（ディレクトリがなければ作成）

---

### Phase 4: 結果の提示

#### 対話的モード（デフォルト）

`/kaizen:present-staged` Skill にレビュー結果ファイルを渡して呼び出す:

```
/kaizen:present-staged .claude/.temp/review-result-{timestamp}.md
```

`/kaizen:present-staged` が段階的・対話的に結果を提示し、修正アクションを処理する。

#### --auto-fix モード

`/kaizen:present-staged` は呼び出さない。サマリーを報告する:

```
## AIレビュー結果
- 🔴致命的: X件（修正済み: Y件）
- 🟡品質: X件
- 🟢改善: X件
```

🔴が残存する場合は、サマリーに加えて残存🔴の具体的内容を表示し、ユーザーに対応を確認する:

```
### 残存する🔴致命的問題
1. **[問題名]**: [説明]
   - 自動修正できなかった理由: ...

→ 対話的モードで解決する / このまま進める
```

呼び出し元ワークフローに制御を返す。

---

## レビュー結果フォーマット

```markdown
## AIレビュー結果

### 🔴致命的問題
1. **[問題名]**: [具体的な説明]
   - 箇所: [ファイル名:行番号 / セクション名]
   - 参照: [関連ルール/要件定義書]
   - 修正案: [具体的な修正提案]

### 🟡品質問題
1. **[問題名]**: [具体的な説明]
   - 箇所: [ファイル名:行番号 / セクション名]

### 🟢改善提案
1. **[提案名]**: [具体的な説明]

### サマリー
- 🔴致命的: X件（修正済み: Y件）
- 🟡品質: X件
- 🟢改善: X件
```

---

## レビュー種別ごとの参考文書

| レビュー種別 | DocAdvisor Skill（利用可能時） | .doc_structure.yaml フォールバック |
|-------------|-------------------------------|----------------------------------|
| 要件定義書 | /query-rules: 関連ルール文書 / /query-specs: 関連要件定義書 | rules パスから Glob + specs パスから Glob |
| 設計書 | /query-rules: 関連ルール文書 / /query-specs: 関連要件定義書・設計書 | rules パスから Glob + specs パスから Glob |
| 計画書 | /query-rules: 関連ルール文書 / /query-specs: 関連要件定義書・設計書 | rules パスから Glob + specs パスから Glob |
| コード | /query-rules: 関連ルール文書 / /query-specs: 関連要件定義書・設計書 | rules パスから Glob + specs パスから Glob |
| 汎用文書 | **不使用**（レビュアーが自発探索） | **不使用** |
