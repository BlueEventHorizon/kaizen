#!/usr/bin/env python3
"""
classify_dirs.py のテスト

ディレクトリ自動分類ロジック、front matter パース、doc_type 推定、
集約、出力フォーマットをテストする。
標準ライブラリのみ使用。

実行:
  python3 -m unittest tests.doc_structure.test_classify_dirs -v
"""

import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

# テスト対象モジュールへのパスを追加
sys.path.insert(0, str(Path(__file__).resolve().parents[2]
                       / 'plugins' / 'doc-structure' / 'scripts'))

from classify_dirs import (
    SKIP_DIRS,
    SKIP_INDICATORS,
    DOC_TYPE_NAMES,
    extract_front_matter,
    classify_by_frontmatter,
    classify_by_dirname,
    score_file_terms,
    classify_by_terms,
    classify_directory,
    estimate_doc_type,
    is_readme_only,
    find_md_dirs,
    aggregate_to_top_dirs,
    build_doc_structure,
    output_doc_structure,
    output_yaml,
    output_summary,
)


class _FsTestCase(unittest.TestCase):
    """ファイルシステムを使うテストの基底クラス"""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_file(self, rel_path, content=''):
        p = self.tmpdir / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding='utf-8')
        return p


# =========================================================================
# 1. Front matter パーステスト
# =========================================================================

class TestExtractFrontMatter(_FsTestCase):
    """extract_front_matter のテスト"""

    def test_valid_front_matter(self):
        f = self._write_file('doc.md', '---\ndoc_type: requirement\ntitle: Test\n---\n# Body')
        fm = extract_front_matter(f)
        self.assertIsNotNone(fm)
        self.assertEqual(fm['doc_type'], 'requirement')
        self.assertEqual(fm['title'], 'Test')

    def test_no_front_matter(self):
        f = self._write_file('doc.md', '# Just markdown\nNo front matter here.')
        fm = extract_front_matter(f)
        self.assertIsNone(fm)

    def test_empty_file(self):
        f = self._write_file('doc.md', '')
        fm = extract_front_matter(f)
        self.assertIsNone(fm)

    def test_incomplete_front_matter(self):
        """閉じ --- がない場合"""
        f = self._write_file('doc.md', '---\ndoc_type: requirement\nNo closing')
        fm = extract_front_matter(f)
        self.assertIsNone(fm)

    def test_quoted_values(self):
        f = self._write_file('doc.md', '---\ntitle: "Quoted Value"\n---\n')
        fm = extract_front_matter(f)
        self.assertEqual(fm['title'], 'Quoted Value')

    def test_nonexistent_file(self):
        fm = extract_front_matter(self.tmpdir / 'nonexistent.md')
        self.assertIsNone(fm)

    def test_comment_lines_skipped(self):
        f = self._write_file('doc.md', '---\n# comment\ndoc_type: design\n---\n')
        fm = extract_front_matter(f)
        self.assertEqual(fm['doc_type'], 'design')
        self.assertNotIn('#', fm)


# =========================================================================
# 2. 分類テスト
# =========================================================================

class TestClassifyByFrontmatter(_FsTestCase):
    """classify_by_frontmatter のテスト"""

    def test_rules_by_frontmatter(self):
        self._write_file('rules/coding.md', '---\ndoc_type: rule\n---\n# Rules')
        result = classify_by_frontmatter(str(self.tmpdir), 'rules')
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'rules')

    def test_specs_by_frontmatter(self):
        self._write_file('specs/req.md', '---\ndoc_type: requirement\n---\n# Req')
        result = classify_by_frontmatter(str(self.tmpdir), 'specs')
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'specs')

    def test_no_front_matter(self):
        self._write_file('docs/guide.md', '# Guide\nNo front matter.')
        result = classify_by_frontmatter(str(self.tmpdir), 'docs')
        self.assertIsNone(result)

    def test_no_md_files(self):
        (self.tmpdir / 'empty').mkdir()
        result = classify_by_frontmatter(str(self.tmpdir), 'empty')
        self.assertIsNone(result)

    def test_mixed_front_matter(self):
        """rule と spec が混在する場合、多い方が優先"""
        self._write_file('docs/r1.md', '---\ndoc_type: rule\n---\n')
        self._write_file('docs/r2.md', '---\ndoc_type: rule\n---\n')
        self._write_file('docs/s1.md', '---\ndoc_type: requirement\n---\n')
        result = classify_by_frontmatter(str(self.tmpdir), 'docs')
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'rules')

    def test_high_confidence_all_same(self):
        """全ファイルが同じ doc_type なら high confidence"""
        self._write_file('docs/d1.md', '---\ndoc_type: design\n---\n')
        self._write_file('docs/d2.md', '---\ndoc_type: design\n---\n')
        result = classify_by_frontmatter(str(self.tmpdir), 'docs')
        self.assertEqual(result[1], 'high')


class TestClassifyByDirname(unittest.TestCase):
    """classify_by_dirname のテスト"""

    def test_rules_dirname(self):
        result = classify_by_dirname('project/rules')
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'rules')

    def test_specs_dirname(self):
        result = classify_by_dirname('project/specs')
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'specs')

    def test_requirements_dirname(self):
        result = classify_by_dirname('specs/login/requirements')
        self.assertEqual(result[0], 'specs')

    def test_design_dirname(self):
        result = classify_by_dirname('docs/design')
        self.assertEqual(result[0], 'specs')

    def test_guidelines_dirname(self):
        result = classify_by_dirname('docs/guidelines')
        self.assertEqual(result[0], 'rules')

    def test_unknown_dirname(self):
        result = classify_by_dirname('docs/misc')
        self.assertIsNone(result)

    def test_nested_match(self):
        """パスの途中にある部分もマッチする"""
        result = classify_by_dirname('some/rules/coding')
        self.assertEqual(result[0], 'rules')

    def test_case_insensitive(self):
        """大文字ディレクトリ名も lower() で比較されマッチする"""
        result = classify_by_dirname('docs/Rules')
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'rules')


class TestScoreFileTerms(_FsTestCase):
    """score_file_terms のテスト"""

    def test_rule_terms(self):
        f = self._write_file('doc.md',
                             'You must follow the coding convention. '
                             'This standard shall be followed. '
                             'Naming guidelines must not be violated.')
        rule, spec = score_file_terms(f)
        self.assertGreater(rule, spec)

    def test_spec_terms(self):
        f = self._write_file('doc.md',
                             'This feature requirement describes the API design. '
                             'The architecture component must implement the specification.')
        rule, spec = score_file_terms(f)
        self.assertGreater(spec, rule)

    def test_empty_file(self):
        f = self._write_file('doc.md', '')
        rule, spec = score_file_terms(f)
        self.assertEqual(rule, 0)
        self.assertEqual(spec, 0)

    def test_nonexistent_file(self):
        rule, spec = score_file_terms(self.tmpdir / 'nonexistent.md')
        self.assertEqual(rule, 0)
        self.assertEqual(spec, 0)


class TestClassifyByTerms(_FsTestCase):
    """classify_by_terms のテスト"""

    def test_rules_by_terms(self):
        self._write_file('docs/r.md',
                         'All developers must follow the convention. '
                         'This standard is mandatory. Naming rule applies. '
                         'This policy shall be followed. Guidelines prohibit this.')
        result = classify_by_terms(str(self.tmpdir), 'docs')
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'rules')

    def test_specs_by_terms(self):
        self._write_file('docs/s.md',
                         'The feature requirement describes the API specification. '
                         'Architecture component and design of the interface. '
                         'Use case acceptance criteria and user story plan.')
        result = classify_by_terms(str(self.tmpdir), 'docs')
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'specs')

    def test_no_terms(self):
        self._write_file('docs/generic.md', 'Hello world.')
        result = classify_by_terms(str(self.tmpdir), 'docs')
        self.assertIsNone(result)

    def test_no_md_files(self):
        (self.tmpdir / 'empty').mkdir()
        result = classify_by_terms(str(self.tmpdir), 'empty')
        self.assertIsNone(result)


class TestClassifyDirectory(_FsTestCase):
    """classify_directory のテスト（3段階フォールバック）"""

    def test_frontmatter_priority(self):
        """front matter が最優先"""
        self._write_file('rules/coding.md', '---\ndoc_type: rule\n---\n# Coding')
        result = classify_directory(str(self.tmpdir), 'rules')
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'rules')
        self.assertIn('frontmatter', result[2])

    def test_dirname_fallback(self):
        """front matter なし → ディレクトリ名にフォールバック"""
        self._write_file('specs/overview.md', '# Overview\nSome content.')
        result = classify_directory(str(self.tmpdir), 'specs')
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 'specs')
        self.assertIn('dirname', result[2])

    def test_terms_fallback(self):
        """front matter なし + ディレクトリ名不明 → 用語ランキングにフォールバック"""
        self._write_file('docs/d.md',
                         'All developers must follow the convention. '
                         'This standard is mandatory. Naming rule applies. '
                         'Do not violate. Policy compliance required. '
                         'This guideline is a best practice.')
        result = classify_directory(str(self.tmpdir), 'docs')
        self.assertIsNotNone(result)
        self.assertIn('term_ranking', result[2])

    def test_unclassifiable(self):
        """全手法で判定不能 → None"""
        self._write_file('misc/note.md', 'Just a short note.')
        result = classify_directory(str(self.tmpdir), 'misc')
        self.assertIsNone(result)


# =========================================================================
# 3. doc_type 推定テスト
# =========================================================================

class TestEstimateDocType(unittest.TestCase):
    """estimate_doc_type のテスト"""

    def test_requirements_dir(self):
        self.assertEqual(estimate_doc_type('specs/login/requirements/', 'specs'), 'requirement')

    def test_design_dir(self):
        self.assertEqual(estimate_doc_type('specs/login/design/', 'specs'), 'design')

    def test_plan_dir(self):
        self.assertEqual(estimate_doc_type('specs/login/plan/', 'specs'), 'plan')

    def test_rules_dir(self):
        self.assertEqual(estimate_doc_type('rules/', 'rules'), 'rule')

    def test_workflow_dir(self):
        self.assertEqual(estimate_doc_type('rules/workflow/', 'rules'), 'workflow')

    def test_guide_dir(self):
        self.assertEqual(estimate_doc_type('docs/guidelines/', 'rules'), 'guide')

    def test_api_dir(self):
        self.assertEqual(estimate_doc_type('docs/api/', 'specs'), 'api')

    def test_unknown_specs_default(self):
        """不明なパスは category に応じたデフォルト"""
        self.assertEqual(estimate_doc_type('docs/misc/', 'specs'), 'spec')

    def test_unknown_rules_default(self):
        self.assertEqual(estimate_doc_type('docs/misc/', 'rules'), 'rule')

    def test_deepest_part_wins(self):
        """reversed(parts) なので最深部が優先"""
        self.assertEqual(estimate_doc_type('specs/requirements/design/', 'specs'), 'design')

    def test_known_doc_type_names(self):
        """DOC_TYPE_NAMES の主要エントリを確認"""
        for dirname, expected in [('requirements', 'requirement'), ('req', 'requirement'),
                                  ('designs', 'design'), ('plans', 'plan'),
                                  ('standards', 'rule'), ('conventions', 'rule')]:
            self.assertEqual(estimate_doc_type(f'docs/{dirname}/', 'specs'), expected,
                             f'{dirname} → {expected}')


# =========================================================================
# 4. ファイルシステム探索テスト
# =========================================================================

class TestIsReadmeOnly(_FsTestCase):
    """is_readme_only のテスト"""

    def test_readme_only(self):
        self._write_file('docs/README.md', '# Readme')
        self.assertTrue(is_readme_only(str(self.tmpdir), 'docs'))

    def test_readme_and_changelog(self):
        self._write_file('docs/README.md', '# Readme')
        self._write_file('docs/CHANGELOG.md', '# Changes')
        self.assertTrue(is_readme_only(str(self.tmpdir), 'docs'))

    def test_not_readme_only(self):
        self._write_file('docs/README.md', '# Readme')
        self._write_file('docs/guide.md', '# Guide')
        self.assertFalse(is_readme_only(str(self.tmpdir), 'docs'))

    def test_case_insensitive(self):
        """README.md は大文字小文字を区別しない"""
        self._write_file('docs/readme.md', '# Readme')
        self.assertTrue(is_readme_only(str(self.tmpdir), 'docs'))


class TestFindMdDirs(_FsTestCase):
    """find_md_dirs のテスト"""

    def test_find_dirs(self):
        self._write_file('docs/guide.md', '# Guide')
        self._write_file('specs/req.md', '# Req')
        result = find_md_dirs(str(self.tmpdir))
        dirs = [d for d, _ in result]
        self.assertIn('docs', dirs)
        self.assertIn('specs', dirs)

    def test_skip_dirs(self):
        """SKIP_DIRS に含まれるディレクトリは除外"""
        self._write_file('.git/info.md', 'internal')
        self._write_file('node_modules/pkg/README.md', 'pkg')
        self._write_file('docs/guide.md', '# Guide')
        result = find_md_dirs(str(self.tmpdir))
        dirs = [d for d, _ in result]
        self.assertNotIn('.git', dirs)
        self.assertNotIn('node_modules/pkg', dirs)
        self.assertIn('docs', dirs)

    def test_skip_project_indicators(self):
        """SKIP_INDICATORS を含むディレクトリは除外"""
        self._write_file('frontend/package.json', '{}')
        self._write_file('frontend/README.md', '# Frontend')
        result = find_md_dirs(str(self.tmpdir))
        dirs = [d for d, _ in result]
        self.assertNotIn('frontend', dirs)

    def test_root_not_included(self):
        """ルートディレクトリ自体は含まれない"""
        self._write_file('README.md', '# Root')
        result = find_md_dirs(str(self.tmpdir))
        dirs = [d for d, _ in result]
        self.assertNotIn('.', dirs)

    def test_empty_project(self):
        result = find_md_dirs(str(self.tmpdir))
        self.assertEqual(result, [])

    def test_md_count(self):
        self._write_file('docs/a.md', '# A')
        self._write_file('docs/b.md', '# B')
        self._write_file('docs/c.md', '# C')
        result = find_md_dirs(str(self.tmpdir))
        docs_entry = [r for r in result if r[0] == 'docs']
        self.assertEqual(len(docs_entry), 1)
        self.assertEqual(docs_entry[0][1], 3)

    def test_symlink_loop_no_infinite_walk(self):
        """シンボリックリンクループで無限ループ・重複しない"""
        self._write_file('docs/guide.md', '# Guide')
        loop_link = self.tmpdir / 'docs' / 'self'
        try:
            os.symlink(str(self.tmpdir / 'docs'), str(loop_link))
        except (OSError, NotImplementedError):
            self.skipTest('symlink を作成できない環境')
        result = find_md_dirs(str(self.tmpdir))
        dirs = [d for d, _ in result]
        # docs は1回だけ出現する（ループで重複しない）
        self.assertEqual(dirs.count('docs'), 1)

    def test_symlink_to_parent_no_infinite_walk(self):
        """親ディレクトリへの symlink でも無限ループしない"""
        self._write_file('docs/guide.md', '# Guide')
        loop_link = self.tmpdir / 'docs' / 'parent'
        try:
            os.symlink(str(self.tmpdir), str(loop_link))
        except (OSError, NotImplementedError):
            self.skipTest('symlink を作成できない環境')
        result = find_md_dirs(str(self.tmpdir))
        dirs = [d for d, _ in result]
        self.assertEqual(dirs.count('docs'), 1)


# =========================================================================
# 5. 集約・構造生成テスト
# =========================================================================

class TestAggregateToTopDirs(unittest.TestCase):
    """aggregate_to_top_dirs のテスト"""

    def test_single_category(self):
        classified = [
            ('rules/coding', 'rules', 'high', 'dirname'),
            ('rules/naming', 'rules', 'medium', 'dirname'),
        ]
        result = aggregate_to_top_dirs(classified)
        self.assertEqual(len(result['rules']), 1)
        self.assertEqual(result['rules'][0]['dir'], 'rules/')

    def test_mixed_categories_under_same_top(self):
        """同じ top-level ディレクトリに rules と specs が混在"""
        classified = [
            ('docs/rules', 'rules', 'medium', 'dirname'),
            ('docs/specs', 'specs', 'medium', 'dirname'),
        ]
        result = aggregate_to_top_dirs(classified)
        self.assertTrue(len(result['rules']) >= 1)
        self.assertTrue(len(result['specs']) >= 1)

    def test_single_subdir_not_aggregated(self):
        """サブディレクトリ1つだけの場合、そのパスを保持"""
        classified = [
            ('docs/requirements', 'specs', 'medium', 'dirname'),
        ]
        result = aggregate_to_top_dirs(classified)
        self.assertEqual(result['specs'][0]['dir'], 'docs/requirements/')

    def test_empty_input(self):
        result = aggregate_to_top_dirs([])
        self.assertEqual(result['rules'], [])
        self.assertEqual(result['specs'], [])

    def test_confidence_high_wins_over_medium(self):
        """high と medium が混在する場合、集約後は high"""
        classified = [
            ('rules/coding', 'rules', 'medium', 'dirname'),
            ('rules/naming', 'rules', 'high', 'term_ranking'),
        ]
        result = aggregate_to_top_dirs(classified)
        self.assertEqual(result['rules'][0]['confidence'], 'high')

    def test_confidence_not_lexicographic(self):
        """confidence 比較が辞書順（m > h）ではなく意味順（high > medium）"""
        classified = [
            ('rules/a', 'rules', 'high', 'test'),
            ('rules/b', 'rules', 'medium', 'test'),
            ('rules/c', 'rules', 'low', 'test'),
        ]
        result = aggregate_to_top_dirs(classified)
        self.assertEqual(result['rules'][0]['confidence'], 'high')

    def test_different_doc_types_not_collapsed(self):
        """同じ top_dir 配下で異なる doc_type は集約しない"""
        classified = [
            ('specs/requirements', 'specs', 'high', 'dirname'),
            ('specs/design', 'specs', 'high', 'dirname'),
        ]
        result = aggregate_to_top_dirs(classified)
        # 2つの個別パスが保持される（specs/ に潰されない）
        self.assertEqual(len(result['specs']), 2)
        dirs = sorted(e['dir'] for e in result['specs'])
        self.assertEqual(dirs, ['specs/design/', 'specs/requirements/'])

    def test_same_doc_type_still_aggregated(self):
        """同一 doc_type のサブディレクトリは従来通り集約"""
        classified = [
            ('rules/coding', 'rules', 'high', 'dirname'),
            ('rules/naming', 'rules', 'medium', 'dirname'),
        ]
        result = aggregate_to_top_dirs(classified)
        self.assertEqual(len(result['rules']), 1)
        self.assertEqual(result['rules'][0]['dir'], 'rules/')

    def test_doc_type_preserved_in_output(self):
        """集約結果に doc_type が含まれる"""
        classified = [
            ('specs/requirements', 'specs', 'high', 'dirname'),
        ]
        result = aggregate_to_top_dirs(classified)
        self.assertEqual(result['specs'][0].get('doc_type'), 'requirement')


class TestBuildDocStructure(unittest.TestCase):
    """build_doc_structure のテスト"""

    def test_basic_structure(self):
        classification = {
            'specs': [
                {'dir': 'specs/requirements/', 'confidence': 'high', 'reason': 'test'},
                {'dir': 'specs/design/', 'confidence': 'high', 'reason': 'test'},
            ],
            'rules': [
                {'dir': 'rules/', 'confidence': 'high', 'reason': 'test'},
            ],
        }
        result = build_doc_structure(classification)

        self.assertIn('specs', result)
        self.assertIn('rules', result)
        self.assertIn('requirement', result['specs'])
        self.assertIn('design', result['specs'])
        self.assertEqual(result['specs']['requirement']['paths'], ['specs/requirements/'])
        self.assertEqual(result['rules']['rule']['paths'], ['rules/'])

    def test_multiple_paths_same_doc_type(self):
        """同じ doc_type に複数パスが集約される"""
        classification = {
            'specs': [
                {'dir': 'specs/requirements/', 'confidence': 'high', 'reason': 'test'},
                {'dir': 'modules/requirements/', 'confidence': 'high', 'reason': 'test'},
            ],
        }
        result = build_doc_structure(classification)
        self.assertEqual(len(result['specs']['requirement']['paths']), 2)

    def test_empty_classification(self):
        result = build_doc_structure({'specs': [], 'rules': []})
        self.assertEqual(result, {})

    def test_doc_type_from_entry(self):
        """entry に doc_type があればそれを使う（estimate_doc_type ではなく）"""
        classification = {
            'specs': [
                {'dir': 'specs/', 'confidence': 'high', 'reason': 'test',
                 'doc_type': 'requirement'},
            ],
        }
        result = build_doc_structure(classification)
        # specs/ → estimate_doc_type なら 'spec' になるが、entry の doc_type を優先
        self.assertIn('requirement', result['specs'])
        self.assertNotIn('spec', result['specs'])

    def test_doc_type_fallback_to_estimate(self):
        """entry に doc_type がなければ estimate_doc_type にフォールバック"""
        classification = {
            'specs': [
                {'dir': 'specs/requirements/', 'confidence': 'high', 'reason': 'test'},
            ],
        }
        result = build_doc_structure(classification)
        self.assertIn('requirement', result['specs'])


# =========================================================================
# 6. 出力フォーマットテスト
# =========================================================================

class TestOutputDocStructure(unittest.TestCase):
    """output_doc_structure のテスト"""

    def _capture(self, classification):
        buf = io.StringIO()
        with redirect_stdout(buf):
            output_doc_structure(classification)
        return buf.getvalue()

    def test_basic_output(self):
        classification = {
            'specs': [
                {'dir': 'specs/requirements/', 'confidence': 'high', 'reason': 'test'},
            ],
            'rules': [
                {'dir': 'rules/', 'confidence': 'high', 'reason': 'test'},
            ],
        }
        output = self._capture(classification)
        self.assertIn('version: "1.0"', output)
        self.assertIn('specs:', output)
        self.assertIn('requirement:', output)
        self.assertIn('paths: [specs/requirements/]', output)
        self.assertIn('rules:', output)

    def test_empty_output(self):
        output = self._capture({'specs': [], 'rules': []})
        self.assertIn('version: "1.0"', output)
        self.assertNotIn('specs:', output)


class TestOutputSummary(unittest.TestCase):
    """output_summary のテスト"""

    def _capture(self, classification):
        buf = io.StringIO()
        with redirect_stdout(buf):
            output_summary(classification)
        return buf.getvalue()

    def test_with_entries(self):
        classification = {
            'rules': [{'dir': 'rules/', 'confidence': 'high', 'reason': 'dirname'}],
            'specs': [],
            'skip': [],
        }
        output = self._capture(classification)
        self.assertIn('rules:', output)
        self.assertIn('type=rule', output)

    def test_empty(self):
        output = self._capture({'rules': [], 'specs': [], 'skip': []})
        self.assertIn('No document directories detected', output)

    def test_skip_entries(self):
        classification = {
            'rules': [], 'specs': [],
            'skip': [{'dir': 'docs/', 'reason': 'README/CHANGELOG only'}],
        }
        output = self._capture(classification)
        self.assertIn('skipped:', output)


class TestOutputYaml(unittest.TestCase):
    """output_yaml のテスト"""

    def test_basic(self):
        classification = {
            'rules': [{'dir': 'rules/', 'confidence': 'high', 'reason': 'dirname'}],
            'specs': [{'dir': 'specs/requirements/', 'confidence': 'medium', 'reason': 'terms'}],
            'skip': [],
            'mixed': [],
        }
        buf = io.StringIO()
        with redirect_stdout(buf):
            output_yaml(classification)
        output = buf.getvalue()
        self.assertIn('classification:', output)
        self.assertIn('doc_type: rule', output)
        self.assertIn('doc_type: requirement', output)


# =========================================================================
# 7. 定数の健全性テスト
# =========================================================================

class TestConstants(unittest.TestCase):
    """定数の健全性を検証"""

    def test_skip_dirs_no_path_separator(self):
        """SKIP_DIRS にパス区切りが含まれていない"""
        for d in SKIP_DIRS:
            self.assertFalse('/' in d, f'SKIP_DIRS にパス区切り: {d}')

    def test_doc_type_names_lowercase_keys(self):
        for key in DOC_TYPE_NAMES:
            self.assertEqual(key, key.lower(),
                             f'DOC_TYPE_NAMES のキーに大文字: {key}')

    def test_skip_indicators_are_filenames(self):
        for ind in SKIP_INDICATORS:
            self.assertFalse('/' in ind,
                             f'SKIP_INDICATORS にパス区切り: {ind}')


if __name__ == '__main__':
    unittest.main()
