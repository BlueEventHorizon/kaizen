#!/usr/bin/env python3
"""
レビュー対象の検出と種別判定スクリプト

.doc_structure.yaml を参照してプロジェクト構造を把握し、
レビュー対象ファイル・種別を特定する。
.doc_structure.yaml がない場合はエラーを返す。

標準ライブラリのみ使用（pyyaml 不要）。

Usage:
  python3 resolve_review_context.py [target1] [target2] ...

  target: ファイルパス（複数可）、ディレクトリパス、Feature名、または省略
  フラグ（--codex, --claude, --auto-fix）は無視される

Output (JSON):
  {
    "status": "resolved" | "needs_input" | "error",
    "has_doc_structure": true | false,
    "type": "requirement" | "design" | "code" | "plan" | "generic" | null,
    "target_files": ["path1", ...],
    "features": ["feature1", ...],
    "questions": [
      {"key": "type|feature|target", "message": "...", "options": [...]}
    ],
    "error": "エラーメッセージ（status=error 時のみ）"
  }
"""

import glob
import json
import os
import sys
from pathlib import Path

# ソースコード拡張子（汎用）
CODE_EXTENSIONS = {'.swift', '.kt', '.java', '.ts', '.tsx', '.js', '.jsx',
                   '.py', '.go', '.rs', '.c', '.cpp', '.h', '.m', '.mm'}

# generic 種別の基盤文書パターン（rules パスは doc_structure から動的取得）
GENERIC_BASE_PATTERNS = [
    '.claude/skills/',
    '.claude/commands/',
]
GENERIC_ROOT_FILES = {'CLAUDE.md', 'README.md'}

# specs doc_type → review type マッピング
SPECS_REVIEW_TYPE_MAP = {
    'requirement': 'requirement',
    'design': 'design',
    'plan': 'plan',
}


# ---------------------------------------------------------------------------
# .doc_structure.yaml パーサー（標準ライブラリのみ、専用スキーマ）
# ---------------------------------------------------------------------------

def _split_kv(s):
    """'key: value' を分割。値がない場合は空文字列"""
    key, _, val = s.partition(':')
    return key.strip(), val.strip()


def _parse_flow_array(s):
    """フロー配列 '[a, b, c]' をパース"""
    inner = s.strip()[1:-1]  # [ ] を除去
    if not inner.strip():
        return []
    return [item.strip().strip('"\'') for item in inner.split(',') if item.strip()]


def _parse_doc_structure_yaml(filepath):
    """.doc_structure.yaml 専用パーサー（インデントベース状態マシン）"""
    result = {}
    current_category = None  # 'specs' or 'rules'
    current_doc_type = None
    current_field = None

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.rstrip()
            if not stripped or stripped.lstrip().startswith('#'):
                continue

            indent = len(line) - len(line.lstrip())
            content = stripped.strip()

            # indent=0: トップレベルキー (version, specs, rules)
            if indent == 0 and ':' in content:
                key, val = _split_kv(content)
                if key == 'version':
                    result['version'] = val.strip('"\'')
                elif key in ('specs', 'rules'):
                    current_category = key
                    result.setdefault(current_category, {})
                    current_doc_type = None
                    current_field = None
                continue

            # indent=2: doc_type キー
            if indent == 2 and current_category and ':' in content:
                key, _ = _split_kv(content)
                current_doc_type = key
                result[current_category].setdefault(current_doc_type, {})
                current_field = None
                continue

            # indent=4: フィールド (paths, description)
            if indent == 4 and current_category and current_doc_type:
                if ':' in content and not content.startswith('- '):
                    key, val = _split_kv(content)
                    current_field = key
                    if key == 'paths':
                        if val.startswith('['):
                            result[current_category][current_doc_type]['paths'] = _parse_flow_array(val)
                            current_field = None
                        else:
                            result[current_category][current_doc_type]['paths'] = []
                    elif key == 'description':
                        result[current_category][current_doc_type]['description'] = val.strip('"\'')
                elif content.startswith('- ') and current_field == 'paths':
                    path_val = content[2:].strip().strip('"\'')
                    result[current_category][current_doc_type].setdefault('paths', []).append(path_val)
                continue

            # indent=6: ブロック配列要素
            if indent == 6 and current_field == 'paths' and content.startswith('- '):
                path_val = content[2:].strip().strip('"\'')
                result[current_category][current_doc_type].setdefault('paths', []).append(path_val)
                continue

    return result if result.get('version') else None


def parse_doc_structure(project_root):
    """.doc_structure.yaml を読み込み。存在しなければ None を返す"""
    filepath = project_root / '.doc_structure.yaml'
    if not filepath.exists():
        return None
    try:
        return _parse_doc_structure_yaml(filepath)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# doc_type → review type マッピング
# ---------------------------------------------------------------------------

def _doc_type_to_review_type(category, doc_type_name):
    """doc_structure の category + doc_type_name からレビュー種別を返す"""
    if category == 'specs':
        return SPECS_REVIEW_TYPE_MAP.get(doc_type_name, 'generic')
    elif category == 'rules':
        return 'generic'
    return None


# ---------------------------------------------------------------------------
# パスマッチング・種別判定
# ---------------------------------------------------------------------------

def _path_matches_pattern(file_path, pattern):
    """ファイルパスがパターン配下にあるか判定。glob * に対応"""
    pattern_parts = pattern.rstrip('/').split('/')
    path_parts = file_path.replace('\\', '/').split('/')

    if len(path_parts) < len(pattern_parts):
        return False

    for i, p_part in enumerate(pattern_parts):
        if p_part == '*':
            continue
        if path_parts[i] != p_part:
            return False
    return True


def detect_type_from_doc_structure(path_str, doc_structure):
    """doc_structure のパス定義を使ってファイルの種別を判定"""
    if not doc_structure:
        return None

    normalized = path_str.replace('\\', '/')
    for category in ('specs', 'rules'):
        for doc_type_name, type_info in doc_structure.get(category, {}).items():
            for declared_path in type_info.get('paths', []):
                if _path_matches_pattern(normalized, declared_path):
                    return _doc_type_to_review_type(category, doc_type_name)
    return None


def get_rules_paths(doc_structure):
    """rules カテゴリの全パスを取得"""
    if not doc_structure:
        return []
    paths = []
    for type_info in doc_structure.get('rules', {}).values():
        paths.extend(type_info.get('paths', []))
    return paths


def get_specs_paths_by_type(doc_structure, review_type):
    """指定 review type に対応する specs パスを取得"""
    if not doc_structure:
        return []
    for doc_type_name, type_info in doc_structure.get('specs', {}).items():
        if _doc_type_to_review_type('specs', doc_type_name) == review_type:
            return type_info.get('paths', [])
    return []


# ---------------------------------------------------------------------------
# Feature 検出
# ---------------------------------------------------------------------------

def detect_features_from_doc_structure(project_root, doc_structure):
    """doc_structure の glob パターンから Feature 名を抽出"""
    if not doc_structure:
        return []

    features = set()
    for doc_type_name, type_info in doc_structure.get('specs', {}).items():
        for path_pattern in type_info.get('paths', []):
            parts = path_pattern.rstrip('/').split('/')
            star_indices = [i for i, p in enumerate(parts) if p == '*']
            if not star_indices:
                continue

            star_idx = star_indices[0]
            prefix = '/'.join(parts[:star_idx])
            prefix_dir = project_root / prefix if prefix else project_root

            if not prefix_dir.is_dir():
                continue

            # * の後のサフィックスパーツ
            suffix_parts = parts[star_idx + 1:]

            for entry in prefix_dir.iterdir():
                if not entry.is_dir() or entry.name.startswith('.'):
                    continue
                if suffix_parts:
                    check_path = entry
                    for sp in suffix_parts:
                        check_path = check_path / sp
                    if check_path.is_dir():
                        features.add(entry.name)
                else:
                    features.add(entry.name)

    return sorted(features)


# ---------------------------------------------------------------------------
# 共通ユーティリティ
# ---------------------------------------------------------------------------

def parse_args():
    """引数を解析（フラグと対象を分離）"""
    targets = []
    for arg in sys.argv[1:]:
        if arg.startswith('--'):
            continue
        targets.append(arg)
    return targets


def find_project_root():
    """プロジェクトルートを検出"""
    current = Path.cwd()
    for _ in range(10):
        if (current / ".git").exists() or (current / ".claude").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return Path.cwd()


# ---------------------------------------------------------------------------
# 種別判定
# ---------------------------------------------------------------------------

def _detect_generic_type(path_str, doc_structure=None):
    """generic 種別の判定（基盤文書パターン）"""
    # rules パスを doc_structure から動的取得
    rules_paths = get_rules_paths(doc_structure) if doc_structure else ['rules/']
    all_patterns = GENERIC_BASE_PATTERNS + rules_paths

    for pattern in all_patterns:
        if path_str.startswith(pattern) or f'/{pattern}' in path_str:
            return "generic"

    filename = Path(path_str).name
    if filename in GENERIC_ROOT_FILES and '/' not in path_str.rstrip('/'):
        return "generic"
    return None


def detect_type_from_path(path_str, doc_structure, project_root):
    """パスから種別を判定"""
    # 1. コードファイル判定（拡張子ベース）
    _, ext = os.path.splitext(path_str)
    if ext.lower() in CODE_EXTENSIONS:
        return "code"

    # 2. .doc_structure.yaml パスマッチ
    ds_type = detect_type_from_doc_structure(path_str, doc_structure)
    if ds_type:
        return ds_type

    # 3. 基盤文書パターン → generic
    generic_type = _detect_generic_type(path_str, doc_structure)
    if generic_type:
        return generic_type

    return None


def detect_type_from_dir(dir_path, doc_structure, project_root):
    """ディレクトリ内のファイルから種別を判定"""
    dir_p = project_root / dir_path
    if not dir_p.is_dir():
        return None, []

    code_files = []
    for ext in CODE_EXTENSIONS:
        code_files.extend(glob.glob(str(dir_p / '**' / f'*{ext}'), recursive=True))

    md_files = sorted(glob.glob(str(dir_p / '**' / '*.md'), recursive=True))

    if code_files:
        # コード+md 混在（src/ に README.md がある等）も code として扱う
        rel_files = [str(Path(f).relative_to(project_root)) for f in code_files]
        return "code", sorted(rel_files)
    elif md_files:
        first_rel = str(Path(md_files[0]).relative_to(project_root))
        review_type = detect_type_from_path(first_rel, doc_structure, project_root)
        rel_files = [str(Path(f).relative_to(project_root)) for f in md_files]
        return review_type, sorted(rel_files)

    return None, []


# ---------------------------------------------------------------------------
# Feature 解決
# ---------------------------------------------------------------------------

def find_feature_subdirs(project_root, doc_structure, feature):
    """Feature 内で存在する種別サブディレクトリを検出（doc_structure ベース）"""
    available = []
    if not doc_structure:
        return available

    for doc_type_name, type_info in doc_structure.get('specs', {}).items():
        review_type = _doc_type_to_review_type('specs', doc_type_name)
        for path_pattern in type_info.get('paths', []):
            if '*' not in path_pattern:
                continue
            # パターン中の * を feature 名に置換して存在確認
            concrete = path_pattern.replace('*', feature, 1)
            concrete_dir = project_root / concrete.rstrip('/')
            if concrete_dir.is_dir() and any(concrete_dir.rglob('*.md')):
                if review_type not in available:
                    available.append(review_type)
    return available


def find_target_files(project_root, doc_structure, feature, review_type):
    """Feature + 種別からファイル一覧を取得（doc_structure ベース）"""
    if not doc_structure:
        return []

    for doc_type_name, type_info in doc_structure.get('specs', {}).items():
        if _doc_type_to_review_type('specs', doc_type_name) != review_type:
            continue
        for path_pattern in type_info.get('paths', []):
            if '*' not in path_pattern:
                continue
            concrete = path_pattern.replace('*', feature, 1)
            pattern = str(project_root / concrete.rstrip('/') / '**' / '*.md')
            files = sorted(glob.glob(pattern, recursive=True))
            if files:
                return [str(Path(f).relative_to(project_root)) for f in files]
    return []


# ---------------------------------------------------------------------------
# 対象解決
# ---------------------------------------------------------------------------

def _resolve_single_target(target, doc_structure, project_root, features, result):
    """単一の対象（ファイル/ディレクトリ/Feature名）を解決"""
    target_path = Path(target)

    if (project_root / target_path).is_file():
        result["type"] = detect_type_from_path(target, doc_structure, project_root)
        result["target_files"] = [target]

        if result["type"] is None:
            result["questions"].append({
                "key": "type",
                "message": f"'{target}' のレビュー種別を判定できません。種別を選択してください。",
                "options": ["requirement", "design", "plan", "code", "generic"]
            })

    elif (project_root / target_path).is_dir():
        detected_type, files = detect_type_from_dir(target, doc_structure, project_root)
        result["type"] = detected_type
        result["target_files"] = files

        if detected_type is None and files:
            result["questions"].append({
                "key": "type",
                "message": f"ディレクトリ '{target}' のレビュー種別を選択してください。",
                "options": ["requirement", "design", "plan", "code", "generic"]
            })
        elif not files:
            result["questions"].append({
                "key": "target",
                "message": f"ディレクトリ '{target}' にレビュー対象ファイルが見つかりません。パスを指定してください。",
                "options": []
            })

    elif target in features:
        available_types = find_feature_subdirs(project_root, doc_structure, target)

        if len(available_types) == 1:
            result["type"] = available_types[0]
            result["target_files"] = find_target_files(
                project_root, doc_structure, target, available_types[0])
        elif len(available_types) > 1:
            result["questions"].append({
                "key": "type",
                "message": f"Feature '{target}' のどの種別をレビューしますか？",
                "options": available_types
            })
        else:
            result["questions"].append({
                "key": "target",
                "message": f"Feature '{target}' にレビュー対象のドキュメントが見つかりません。パスを指定してください。",
                "options": []
            })

    else:
        result["questions"].append({
            "key": "target",
            "message": f"'{target}' が見つかりません。レビュー対象のファイルまたはディレクトリを指定してください。",
            "options": []
        })


def _resolve_multiple_targets(targets, doc_structure, project_root, result):
    """複数ファイル対象を解決"""
    valid_files = []
    missing = []

    for t in targets:
        if (project_root / t).is_file():
            valid_files.append(t)
        else:
            missing.append(t)

    if missing:
        result["questions"].append({
            "key": "target",
            "message": f"以下のファイルが見つかりません: {', '.join(missing)}",
            "options": []
        })
        result["target_files"] = valid_files
        return

    result["target_files"] = valid_files

    # 種別判定: 最初のファイルで判定
    result["type"] = detect_type_from_path(valid_files[0], doc_structure, project_root)

    if result["type"] is None:
        result["questions"].append({
            "key": "type",
            "message": "レビュー種別を判定できません。種別を選択してください。",
            "options": ["requirement", "design", "plan", "code", "generic"]
        })


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main():
    targets = parse_args()

    project_root = find_project_root()
    os.chdir(project_root)

    # .doc_structure.yaml を読み込む（必須）
    doc_structure = parse_doc_structure(project_root)
    has_doc_structure = doc_structure is not None

    if not has_doc_structure:
        # .doc_structure.yaml がなければエラー
        print(json.dumps({
            "status": "error",
            "has_doc_structure": False,
            "type": None,
            "target_files": [],
            "features": [],
            "questions": [],
            "error": ".doc_structure.yaml が見つかりません。/doc-structure:init-doc-structure を実行して作成してください。"
        }, ensure_ascii=False, indent=2))
        return

    features = detect_features_from_doc_structure(project_root, doc_structure)

    result = {
        "status": "resolved",
        "has_doc_structure": True,
        "type": None,
        "target_files": [],
        "features": features,
        "questions": []
    }

    if len(targets) > 1:
        _resolve_multiple_targets(targets, doc_structure, project_root, result)

    elif len(targets) == 1:
        _resolve_single_target(targets[0], doc_structure, project_root,
                               features, result)

    else:
        # 対象未指定
        if features:
            result["questions"].append({
                "key": "feature",
                "message": "レビュー対象の Feature を選択してください（コードレビューの場合はパスを指定）。",
                "options": features
            })
        else:
            result["questions"].append({
                "key": "target",
                "message": "レビュー対象のファイルまたはディレクトリを指定してください。",
                "options": []
            })

    # ステータス判定
    if result["questions"]:
        result["status"] = "needs_input"

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
