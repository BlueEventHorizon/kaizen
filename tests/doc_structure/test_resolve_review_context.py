#!/usr/bin/env python3
"""
resolve_review_context.py のテスト

.doc_structure.yaml パーサー、exclude 判定、種別判定、Feature 検出をテストする。
標準ライブラリのみ使用。

実行:
  python3 tests/doc-structure/test_resolve_review_context.py
  # または
  python3 -m pytest tests/doc-structure/test_resolve_review_context.py -v
"""

import os
import sys
import shutil
import tempfile
import unittest
from pathlib import Path

# テスト対象モジュールへのパスを追加
sys.path.insert(0, str(Path(__file__).resolve().parents[2]
                       / 'plugins' / 'kaizen' / 'skills' / 'review' / 'scripts'))

from resolve_review_context import (
    _parse_doc_structure_yaml,
    _parse_flow_array,
    _split_kv,
    _is_excluded,
    _get_all_excludes,
    _path_matches_pattern,
    _doc_type_to_review_type,
    detect_type_from_doc_structure,
    detect_type_from_path,
    detect_type_from_dir,
    detect_features_from_doc_structure,
    get_rules_paths,
    get_specs_paths_by_type,
    _detect_generic_type,
    find_feature_subdirs,
    find_target_files,
)


# ---------------------------------------------------------------------------
# テスト用 YAML テンプレート
# ---------------------------------------------------------------------------

YAML_WITH_EXCLUDE = """\
version: "1.0"

specs:
  requirement:
    paths: ["specs/*/requirements/"]
    exclude: ["archived", "_template"]
  design:
    paths: ["specs/*/design/"]
    exclude:
      - archived

rules:
  rule:
    paths: [rules/]
"""

YAML_NO_EXCLUDE = """\
version: "1.0"

specs:
  requirement:
    paths: ["specs/*/requirements/"]
  design:
    paths: [specs/design/]
    description: "設計書"

rules:
  rule:
    paths: [rules/]
"""

YAML_FLAT = """\
version: "1.0"

specs:
  requirement:
    paths: [specs/requirements/]
  design:
    paths: [specs/design/]
  plan:
    paths: [specs/plan/]

rules:
  rule:
    paths: [rules/]
"""

YAML_MIXED_EXCLUDE = """\
version: "1.0"

specs:
  requirement:
    paths:
      - "specs/*/requirements/"
      - "modules/*/requirements/"
    exclude:
      - archived
      - _template
      - deprecated
  design:
    paths: ["specs/*/design/"]

rules:
  rule:
    paths: [rules/]
    exclude: ["deprecated"]
"""


class _YamlFileTestCase(unittest.TestCase):
    """YAML ファイルを tmpdir に書き出すヘルパー付きの基底クラス"""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_yaml(self, content, filename='.doc_structure.yaml'):
        path = self.tmpdir / filename
        path.write_text(content, encoding='utf-8')
        return path


# =========================================================================
# 1. パーサーテスト
# =========================================================================

class TestParseFlowArray(unittest.TestCase):
    """_parse_flow_array のテスト"""

    def test_simple(self):
        self.assertEqual(_parse_flow_array('[a, b, c]'), ['a', 'b', 'c'])

    def test_quoted(self):
        self.assertEqual(_parse_flow_array('["a/b/", "c/d/"]'), ['a/b/', 'c/d/'])

    def test_empty(self):
        self.assertEqual(_parse_flow_array('[]'), [])

    def test_single(self):
        self.assertEqual(_parse_flow_array('[rules/]'), ['rules/'])


class TestSplitKv(unittest.TestCase):
    """_split_kv のテスト"""

    def test_normal(self):
        self.assertEqual(_split_kv('paths: [rules/]'), ('paths', '[rules/]'))

    def test_no_value(self):
        self.assertEqual(_split_kv('specs:'), ('specs', ''))

    def test_description(self):
        self.assertEqual(_split_kv('description: "設計書"'), ('description', '"設計書"'))


class TestParseDocStructureYaml(_YamlFileTestCase):
    """_parse_doc_structure_yaml のテスト"""

    def test_exclude_flow_array(self):
        """フロー配列形式の exclude をパースできる"""
        path = self._write_yaml(YAML_WITH_EXCLUDE)
        result = _parse_doc_structure_yaml(path)

        self.assertEqual(result['specs']['requirement']['exclude'],
                         ['archived', '_template'])

    def test_exclude_block_array(self):
        """ブロック配列形式の exclude をパースできる"""
        path = self._write_yaml(YAML_WITH_EXCLUDE)
        result = _parse_doc_structure_yaml(path)

        self.assertEqual(result['specs']['design']['exclude'], ['archived'])

    def test_no_exclude_field(self):
        """exclude がない doc_type には exclude キーが存在しない"""
        path = self._write_yaml(YAML_WITH_EXCLUDE)
        result = _parse_doc_structure_yaml(path)

        self.assertNotIn('exclude', result['rules']['rule'])

    def test_backward_compat_no_exclude(self):
        """exclude なしの YAML が正常にパースされる"""
        path = self._write_yaml(YAML_NO_EXCLUDE)
        result = _parse_doc_structure_yaml(path)

        self.assertEqual(result['specs']['requirement']['paths'],
                         ['specs/*/requirements/'])
        self.assertNotIn('exclude', result['specs']['requirement'])
        self.assertEqual(result['specs']['design']['description'], '設計書')

    def test_multiple_paths_with_exclude(self):
        """複数 paths + 複数 exclude のブロック配列形式"""
        path = self._write_yaml(YAML_MIXED_EXCLUDE)
        result = _parse_doc_structure_yaml(path)

        self.assertEqual(result['specs']['requirement']['paths'],
                         ['specs/*/requirements/', 'modules/*/requirements/'])
        self.assertEqual(result['specs']['requirement']['exclude'],
                         ['archived', '_template', 'deprecated'])

    def test_rules_with_exclude(self):
        """rules カテゴリの exclude もパースされる"""
        path = self._write_yaml(YAML_MIXED_EXCLUDE)
        result = _parse_doc_structure_yaml(path)

        self.assertEqual(result['rules']['rule']['exclude'], ['deprecated'])

    def test_version(self):
        """version が正しく読み取れる"""
        path = self._write_yaml(YAML_WITH_EXCLUDE)
        result = _parse_doc_structure_yaml(path)
        self.assertEqual(result['version'], '1.0')

    def test_no_version_returns_none(self):
        """version がないと None を返す"""
        path = self._write_yaml('specs:\n  requirement:\n    paths: [specs/]')
        result = _parse_doc_structure_yaml(path)
        self.assertIsNone(result)

    def test_flat_structure(self):
        """フラット構造の YAML をパース"""
        path = self._write_yaml(YAML_FLAT)
        result = _parse_doc_structure_yaml(path)

        self.assertEqual(result['specs']['plan']['paths'], ['specs/plan/'])
        self.assertEqual(result['rules']['rule']['paths'], ['rules/'])


# =========================================================================
# 2. Exclude 判定テスト
# =========================================================================

class TestIsExcluded(unittest.TestCase):
    """_is_excluded のテスト"""

    def test_excluded_component(self):
        self.assertTrue(
            _is_excluded('specs/archived/requirements/req.md',
                         ['archived', '_template']))

    def test_excluded_template(self):
        self.assertTrue(
            _is_excluded('specs/_template/requirements/req.md',
                         ['archived', '_template']))

    def test_not_excluded(self):
        self.assertFalse(
            _is_excluded('specs/login/requirements/req.md',
                         ['archived', '_template']))

    def test_empty_list(self):
        self.assertFalse(
            _is_excluded('specs/archived/requirements/req.md', []))

    def test_none_list(self):
        self.assertFalse(
            _is_excluded('specs/archived/requirements/req.md', None))

    def test_deep_nested_excluded(self):
        """パスの深い位置にある exclude 名もマッチする"""
        self.assertTrue(
            _is_excluded('a/b/c/archived/d/e.md', ['archived']))

    def test_partial_name_not_excluded(self):
        """部分一致はマッチしない（archived_v2 != archived）"""
        self.assertFalse(
            _is_excluded('specs/archived_v2/requirements/req.md',
                         ['archived']))

    def test_backslash_path(self):
        """Windows パス区切りもサポート"""
        self.assertTrue(
            _is_excluded('specs\\archived\\requirements\\req.md',
                         ['archived']))


class TestGetAllExcludes(_YamlFileTestCase):
    """_get_all_excludes のテスト"""

    def test_specs_excludes(self):
        path = self._write_yaml(YAML_WITH_EXCLUDE)
        ds = _parse_doc_structure_yaml(path)
        excludes = _get_all_excludes(ds, 'specs')
        self.assertEqual(excludes, {'archived', '_template'})

    def test_rules_no_excludes(self):
        path = self._write_yaml(YAML_WITH_EXCLUDE)
        ds = _parse_doc_structure_yaml(path)
        excludes = _get_all_excludes(ds, 'rules')
        self.assertEqual(excludes, set())

    def test_rules_with_excludes(self):
        path = self._write_yaml(YAML_MIXED_EXCLUDE)
        ds = _parse_doc_structure_yaml(path)
        excludes = _get_all_excludes(ds, 'rules')
        self.assertEqual(excludes, {'deprecated'})

    def test_none_doc_structure(self):
        excludes = _get_all_excludes(None, 'specs')
        self.assertEqual(excludes, set())


# =========================================================================
# 3. パスマッチング・種別判定テスト
# =========================================================================

class TestPathMatchesPattern(unittest.TestCase):
    """_path_matches_pattern のテスト"""

    def test_literal_match(self):
        self.assertTrue(_path_matches_pattern('rules/coding.md', 'rules'))

    def test_literal_nested(self):
        self.assertTrue(
            _path_matches_pattern('specs/requirements/req.md',
                                  'specs/requirements'))

    def test_glob_match(self):
        self.assertTrue(
            _path_matches_pattern('specs/login/requirements/req.md',
                                  'specs/*/requirements'))

    def test_glob_no_match(self):
        self.assertFalse(
            _path_matches_pattern('specs/login/design/d.md',
                                  'specs/*/requirements'))

    def test_shorter_path(self):
        self.assertFalse(
            _path_matches_pattern('specs/login',
                                  'specs/*/requirements'))


class TestDocTypeToReviewType(unittest.TestCase):
    """_doc_type_to_review_type のテスト"""

    def test_specs_requirement(self):
        self.assertEqual(_doc_type_to_review_type('specs', 'requirement'),
                         'requirement')

    def test_specs_design(self):
        self.assertEqual(_doc_type_to_review_type('specs', 'design'), 'design')

    def test_specs_plan(self):
        self.assertEqual(_doc_type_to_review_type('specs', 'plan'), 'plan')

    def test_specs_unknown(self):
        self.assertEqual(_doc_type_to_review_type('specs', 'unknown'), 'generic')

    def test_rules(self):
        self.assertEqual(_doc_type_to_review_type('rules', 'rule'), 'generic')

    def test_invalid_category(self):
        self.assertIsNone(_doc_type_to_review_type('other', 'rule'))


class TestDetectTypeFromDocStructure(_YamlFileTestCase):
    """detect_type_from_doc_structure のテスト"""

    def _get_ds(self, yaml_content=YAML_WITH_EXCLUDE):
        path = self._write_yaml(yaml_content)
        return _parse_doc_structure_yaml(path)

    def test_normal_path_requirement(self):
        ds = self._get_ds()
        self.assertEqual(
            detect_type_from_doc_structure(
                'specs/login/requirements/req.md', ds),
            'requirement')

    def test_normal_path_design(self):
        ds = self._get_ds()
        self.assertEqual(
            detect_type_from_doc_structure(
                'specs/login/design/design.md', ds),
            'design')

    def test_excluded_path_returns_none(self):
        """exclude されたパスは None を返す"""
        ds = self._get_ds()
        self.assertIsNone(
            detect_type_from_doc_structure(
                'specs/archived/requirements/req.md', ds))

    def test_template_excluded(self):
        ds = self._get_ds()
        self.assertIsNone(
            detect_type_from_doc_structure(
                'specs/_template/requirements/req.md', ds))

    def test_design_archived_excluded(self):
        ds = self._get_ds()
        self.assertIsNone(
            detect_type_from_doc_structure(
                'specs/archived/design/d.md', ds))

    def test_rules_no_exclude(self):
        """rules（exclude なし）は従来通りマッチ"""
        ds = self._get_ds()
        self.assertEqual(
            detect_type_from_doc_structure('rules/coding.md', ds),
            'generic')

    def test_no_exclude_backward_compat(self):
        """exclude なしの YAML で archived もマッチする（後方互換）"""
        ds = self._get_ds(YAML_NO_EXCLUDE)
        self.assertEqual(
            detect_type_from_doc_structure(
                'specs/archived/requirements/req.md', ds),
            'requirement')

    def test_none_doc_structure(self):
        self.assertIsNone(
            detect_type_from_doc_structure('specs/login/requirements/req.md', None))


class TestDetectGenericType(_YamlFileTestCase):
    """_detect_generic_type のテスト"""

    def _get_ds(self, yaml_content=YAML_MIXED_EXCLUDE):
        path = self._write_yaml(yaml_content)
        return _parse_doc_structure_yaml(path)

    def test_rules_path(self):
        ds = self._get_ds(YAML_WITH_EXCLUDE)
        self.assertEqual(_detect_generic_type('rules/coding.md', ds), 'generic')

    def test_rules_excluded(self):
        """rules に exclude があるとき、除外パスは generic にならない"""
        ds = self._get_ds(YAML_MIXED_EXCLUDE)
        self.assertIsNone(
            _detect_generic_type('rules/deprecated/old_rule.md', ds))

    def test_rules_not_excluded(self):
        ds = self._get_ds(YAML_MIXED_EXCLUDE)
        self.assertEqual(
            _detect_generic_type('rules/coding/style.md', ds), 'generic')

    def test_skills_path(self):
        self.assertEqual(
            _detect_generic_type('.claude/skills/my-skill/SKILL.md'), 'generic')

    def test_root_readme(self):
        self.assertEqual(_detect_generic_type('README.md'), 'generic')

    def test_nested_readme(self):
        """ルート以外の README.md は generic にならない"""
        self.assertIsNone(_detect_generic_type('docs/README.md'))

    def test_no_doc_structure(self):
        """doc_structure なしでもデフォルト rules/ でマッチ"""
        self.assertEqual(_detect_generic_type('rules/coding.md'), 'generic')


class TestGetRulesAndSpecsPaths(_YamlFileTestCase):
    """get_rules_paths / get_specs_paths_by_type のテスト"""

    def test_get_rules_paths(self):
        path = self._write_yaml(YAML_FLAT)
        ds = _parse_doc_structure_yaml(path)
        self.assertEqual(get_rules_paths(ds), ['rules/'])

    def test_get_rules_paths_none(self):
        self.assertEqual(get_rules_paths(None), [])

    def test_get_specs_paths_requirement(self):
        path = self._write_yaml(YAML_FLAT)
        ds = _parse_doc_structure_yaml(path)
        self.assertEqual(get_specs_paths_by_type(ds, 'requirement'),
                         ['specs/requirements/'])

    def test_get_specs_paths_design(self):
        path = self._write_yaml(YAML_FLAT)
        ds = _parse_doc_structure_yaml(path)
        self.assertEqual(get_specs_paths_by_type(ds, 'design'),
                         ['specs/design/'])

    def test_get_specs_paths_none(self):
        self.assertEqual(get_specs_paths_by_type(None, 'requirement'), [])


# =========================================================================
# 4. Feature 検出テスト（ファイルシステム必要）
# =========================================================================

class TestDetectFeaturesFromDocStructure(_YamlFileTestCase):
    """detect_features_from_doc_structure のテスト"""

    def _setup_feature_dirs(self, feature_names, excluded_names=None):
        """テスト用のディレクトリ構造を作成"""
        for name in feature_names:
            (self.tmpdir / 'specs' / name / 'requirements').mkdir(parents=True)
            (self.tmpdir / 'specs' / name / 'requirements' / 'req.md').touch()
        for name in (excluded_names or []):
            (self.tmpdir / 'specs' / name / 'requirements').mkdir(parents=True)
            (self.tmpdir / 'specs' / name / 'requirements' / 'req.md').touch()

    def test_features_detected(self):
        self._setup_feature_dirs(['login', 'auth'])
        ds = {
            'version': '1.0',
            'specs': {
                'requirement': {
                    'paths': ['specs/*/requirements/'],
                },
            },
        }
        features = detect_features_from_doc_structure(self.tmpdir, ds)
        self.assertEqual(features, ['auth', 'login'])

    def test_excluded_features_not_detected(self):
        """exclude に含まれるディレクトリは Feature に現れない"""
        self._setup_feature_dirs(['login', 'auth'], ['archived', '_template'])
        ds = {
            'version': '1.0',
            'specs': {
                'requirement': {
                    'paths': ['specs/*/requirements/'],
                    'exclude': ['archived', '_template'],
                },
            },
        }
        features = detect_features_from_doc_structure(self.tmpdir, ds)
        self.assertEqual(features, ['auth', 'login'])
        self.assertNotIn('archived', features)
        self.assertNotIn('_template', features)

    def test_no_exclude_includes_all(self):
        """exclude なしなら全ディレクトリが Feature に含まれる"""
        self._setup_feature_dirs(['login', 'archived'])
        ds = {
            'version': '1.0',
            'specs': {
                'requirement': {
                    'paths': ['specs/*/requirements/'],
                },
            },
        }
        features = detect_features_from_doc_structure(self.tmpdir, ds)
        self.assertIn('archived', features)
        self.assertIn('login', features)

    def test_none_doc_structure(self):
        features = detect_features_from_doc_structure(self.tmpdir, None)
        self.assertEqual(features, [])

    def test_no_glob_pattern(self):
        """glob なしのパスからは Feature を検出しない"""
        (self.tmpdir / 'specs' / 'requirements').mkdir(parents=True)
        ds = {
            'version': '1.0',
            'specs': {
                'requirement': {
                    'paths': ['specs/requirements/'],
                },
            },
        }
        features = detect_features_from_doc_structure(self.tmpdir, ds)
        self.assertEqual(features, [])


# =========================================================================
# 5. Feature 解決テスト（ファイルシステム必要）
# =========================================================================

class TestFindFeatureSubdirs(_YamlFileTestCase):
    """find_feature_subdirs のテスト"""

    def _setup_feature(self, feature, subdirs):
        for sub in subdirs:
            d = self.tmpdir / 'specs' / feature / sub
            d.mkdir(parents=True, exist_ok=True)
            (d / 'doc.md').touch()

    def test_feature_with_requirement(self):
        self._setup_feature('login', ['requirements'])
        ds = {
            'version': '1.0',
            'specs': {
                'requirement': {'paths': ['specs/*/requirements/']},
            },
        }
        types = find_feature_subdirs(self.tmpdir, ds, 'login')
        self.assertEqual(types, ['requirement'])

    def test_excluded_feature_returns_empty(self):
        """exclude に含まれる Feature 名は結果に含まれない"""
        self._setup_feature('archived', ['requirements'])
        ds = {
            'version': '1.0',
            'specs': {
                'requirement': {
                    'paths': ['specs/*/requirements/'],
                    'exclude': ['archived'],
                },
            },
        }
        types = find_feature_subdirs(self.tmpdir, ds, 'archived')
        self.assertEqual(types, [])

    def test_none_doc_structure(self):
        self.assertEqual(find_feature_subdirs(self.tmpdir, None, 'login'), [])


class TestFindTargetFiles(_YamlFileTestCase):
    """find_target_files のテスト"""

    def _setup_feature_files(self, feature, subdir, filenames):
        d = self.tmpdir / 'specs' / feature / subdir
        d.mkdir(parents=True, exist_ok=True)
        for name in filenames:
            (d / name).touch()

    def test_find_files(self):
        self._setup_feature_files('login', 'requirements', ['req1.md', 'req2.md'])
        ds = {
            'version': '1.0',
            'specs': {
                'requirement': {'paths': ['specs/*/requirements/']},
            },
        }
        files = find_target_files(self.tmpdir, ds, 'login', 'requirement')
        self.assertEqual(len(files), 2)
        self.assertTrue(all('login/requirements' in f for f in files))

    def test_excluded_files_filtered(self):
        """exclude パスに含まれるファイルはフィルタされる"""
        self._setup_feature_files('archived', 'requirements', ['req.md'])
        self._setup_feature_files('login', 'requirements', ['req.md'])
        ds = {
            'version': '1.0',
            'specs': {
                'requirement': {
                    'paths': ['specs/*/requirements/'],
                    'exclude': ['archived'],
                },
            },
        }
        # login の Feature を検索 — exclude は archived なので login は見つかる
        files = find_target_files(self.tmpdir, ds, 'login', 'requirement')
        self.assertEqual(len(files), 1)
        self.assertIn('login', files[0])

    def test_none_doc_structure(self):
        self.assertEqual(find_target_files(self.tmpdir, None, 'login', 'requirement'), [])


# =========================================================================
# 6. 種別判定の統合テスト
# =========================================================================

class TestDetectTypeFromPath(_YamlFileTestCase):
    """detect_type_from_path の統合テスト"""

    def _get_ds(self, yaml_content=YAML_WITH_EXCLUDE):
        path = self._write_yaml(yaml_content)
        return _parse_doc_structure_yaml(path)

    def test_code_by_extension(self):
        ds = self._get_ds()
        self.assertEqual(
            detect_type_from_path('src/main.swift', ds, self.tmpdir), 'code')

    def test_python_code(self):
        ds = self._get_ds()
        self.assertEqual(
            detect_type_from_path('scripts/tool.py', ds, self.tmpdir), 'code')

    def test_requirement_from_doc_structure(self):
        ds = self._get_ds()
        self.assertEqual(
            detect_type_from_path(
                'specs/login/requirements/req.md', ds, self.tmpdir),
            'requirement')

    def test_excluded_path_falls_through(self):
        """exclude されたパスは doc_structure でマッチせず、generic 等にフォールスルー"""
        ds = self._get_ds()
        # archived/requirements は exclude → doc_structure マッチなし
        # generic パターンにもマッチしない → None
        result = detect_type_from_path(
            'specs/archived/requirements/req.md', ds, self.tmpdir)
        self.assertIsNone(result)

    def test_generic_from_skills(self):
        ds = self._get_ds()
        self.assertEqual(
            detect_type_from_path(
                '.claude/skills/my-skill/SKILL.md', ds, self.tmpdir),
            'generic')


class TestDetectTypeFromDir(_YamlFileTestCase):
    """detect_type_from_dir のテスト"""

    def test_code_dir(self):
        src = self.tmpdir / 'src'
        src.mkdir()
        (src / 'main.swift').touch()
        ds = {'version': '1.0', 'specs': {}, 'rules': {}}
        review_type, files = detect_type_from_dir('src', ds, self.tmpdir)
        self.assertEqual(review_type, 'code')
        self.assertTrue(len(files) > 0)

    def test_mixed_code_and_md(self):
        """コード + md 混在ディレクトリは code を返す"""
        src = self.tmpdir / 'src'
        src.mkdir()
        (src / 'main.py').touch()
        (src / 'README.md').touch()
        ds = {'version': '1.0', 'specs': {}, 'rules': {}}
        review_type, files = detect_type_from_dir('src', ds, self.tmpdir)
        self.assertEqual(review_type, 'code')

    def test_empty_dir(self):
        empty = self.tmpdir / 'empty'
        empty.mkdir()
        ds = {'version': '1.0', 'specs': {}, 'rules': {}}
        review_type, files = detect_type_from_dir('empty', ds, self.tmpdir)
        self.assertIsNone(review_type)
        self.assertEqual(files, [])

    def test_nonexistent_dir(self):
        ds = {'version': '1.0', 'specs': {}, 'rules': {}}
        review_type, files = detect_type_from_dir('nonexistent', ds, self.tmpdir)
        self.assertIsNone(review_type)
        self.assertEqual(files, [])


if __name__ == '__main__':
    unittest.main()
