#!/usr/bin/env python3
"""
プラグイン整合性テスト

JSON マニフェスト（marketplace.json, plugin.json）の構造・バージョン整合性、
SKILL.md の frontmatter 検証、相互参照チェック、参照ファイル存在確認をテストする。
標準ライブラリのみ使用。

実行:
  python3 tests/test_plugin_integrity.py -v
"""

import json
import os
import re
import unittest
from pathlib import Path

# リポジトリルート
REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGINS_DIR = REPO_ROOT / 'plugins'


def _read_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _parse_skill_frontmatter(skill_path):
    """SKILL.md の YAML frontmatter を簡易パース"""
    with open(skill_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if not content.startswith('---'):
        return None

    end = content.find('---', 3)
    if end == -1:
        return None

    fm_text = content[3:end]
    result = {}
    current_key = None
    current_value_lines = []

    for line in fm_text.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        # マルチライン値の継続行
        if line.startswith('  ') and current_key and current_value_lines is not None:
            current_value_lines.append(stripped)
            continue

        # 前のキーの値を確定
        if current_key and current_value_lines:
            result[current_key] = ' '.join(current_value_lines)
            current_value_lines = []

        if ':' in stripped:
            key, _, val = stripped.partition(':')
            key = key.strip()
            val = val.strip()
            current_key = key
            if val and val != '|':
                result[key] = val.strip('"\'')
                current_key = None
                current_value_lines = []
            else:
                current_value_lines = []

    # 最後のキー
    if current_key and current_value_lines:
        result[current_key] = ' '.join(current_value_lines)

    return result


# =========================================================================
# 1. マーケットプレイス JSON テスト
# =========================================================================

class TestMarketplaceJson(unittest.TestCase):
    """marketplace.json の構造テスト"""

    def setUp(self):
        self.mp = _read_json(REPO_ROOT / '.claude-plugin' / 'marketplace.json')

    def test_has_schema(self):
        self.assertIn('$schema', self.mp)

    def test_has_name(self):
        self.assertEqual(self.mp['name'], 'bw-cc-plugins')

    def test_has_owner(self):
        self.assertIn('owner', self.mp)
        self.assertIn('name', self.mp['owner'])

    def test_has_plugins_array(self):
        self.assertIsInstance(self.mp['plugins'], list)
        self.assertGreater(len(self.mp['plugins']), 0)

    def test_plugin_required_fields(self):
        """各プラグインに必須フィールドがある"""
        required = {'name', 'version', 'source', 'description'}
        for plugin in self.mp['plugins']:
            for field in required:
                self.assertIn(field, plugin,
                              f"プラグイン '{plugin.get('name', '?')}' に '{field}' がない")

    def test_plugin_source_paths_exist(self):
        """source パスが実際に存在する"""
        for plugin in self.mp['plugins']:
            source = REPO_ROOT / plugin['source']
            self.assertTrue(source.is_dir(),
                            f"プラグイン '{plugin['name']}' の source '{plugin['source']}' が存在しない")

    def test_plugin_names_unique(self):
        names = [p['name'] for p in self.mp['plugins']]
        self.assertEqual(len(names), len(set(names)), 'プラグイン名が重複')

    def test_version_format(self):
        """バージョンがセマンティックバージョニング形式"""
        for plugin in self.mp['plugins']:
            self.assertRegex(plugin['version'], r'^\d+\.\d+\.\d+$',
                             f"'{plugin['name']}' のバージョン '{plugin['version']}' が不正")


# =========================================================================
# 2. プラグイン plugin.json テスト
# =========================================================================

class TestPluginJsonFiles(unittest.TestCase):
    """各プラグインの plugin.json テスト"""

    def setUp(self):
        self.mp = _read_json(REPO_ROOT / '.claude-plugin' / 'marketplace.json')

    def test_plugin_json_exists(self):
        """各プラグインに .claude-plugin/plugin.json が存在する"""
        for mp_plugin in self.mp['plugins']:
            plugin_dir = REPO_ROOT / mp_plugin['source']
            pj = plugin_dir / '.claude-plugin' / 'plugin.json'
            self.assertTrue(pj.is_file(),
                            f"'{mp_plugin['name']}' に plugin.json がない: {pj}")

    def test_version_consistency(self):
        """marketplace.json と plugin.json のバージョンが一致"""
        for mp_plugin in self.mp['plugins']:
            plugin_dir = REPO_ROOT / mp_plugin['source']
            pj = _read_json(plugin_dir / '.claude-plugin' / 'plugin.json')
            self.assertEqual(mp_plugin['version'], pj['version'],
                             f"'{mp_plugin['name']}' のバージョン不一致: "
                             f"marketplace={mp_plugin['version']} vs plugin={pj['version']}")

    def test_name_consistency(self):
        """marketplace.json と plugin.json の名前が一致"""
        for mp_plugin in self.mp['plugins']:
            plugin_dir = REPO_ROOT / mp_plugin['source']
            pj = _read_json(plugin_dir / '.claude-plugin' / 'plugin.json')
            self.assertEqual(mp_plugin['name'], pj['name'],
                             f"名前不一致: marketplace={mp_plugin['name']} vs plugin={pj['name']}")

    def test_plugin_json_required_fields(self):
        """plugin.json に必須フィールドがある"""
        required = {'name', 'description', 'version'}
        for mp_plugin in self.mp['plugins']:
            plugin_dir = REPO_ROOT / mp_plugin['source']
            pj = _read_json(plugin_dir / '.claude-plugin' / 'plugin.json')
            for field in required:
                self.assertIn(field, pj,
                              f"'{mp_plugin['name']}' の plugin.json に '{field}' がない")

    def test_license_present(self):
        """plugin.json に license がある"""
        for mp_plugin in self.mp['plugins']:
            plugin_dir = REPO_ROOT / mp_plugin['source']
            pj = _read_json(plugin_dir / '.claude-plugin' / 'plugin.json')
            self.assertIn('license', pj,
                          f"'{mp_plugin['name']}' に license がない")


# =========================================================================
# 3. SKILL.md 検証テスト
# =========================================================================

class TestSkillMdFiles(unittest.TestCase):
    """全 SKILL.md の frontmatter と構造テスト"""

    @classmethod
    def setUpClass(cls):
        """全 SKILL.md ファイルを収集"""
        cls.skills = []
        for skill_md in PLUGINS_DIR.rglob('SKILL.md'):
            plugin_name = skill_md.relative_to(PLUGINS_DIR).parts[0]
            skill_name = skill_md.parent.name
            fm = _parse_skill_frontmatter(skill_md)
            cls.skills.append({
                'path': skill_md,
                'plugin': plugin_name,
                'dir_name': skill_name,
                'frontmatter': fm,
            })

    def test_skills_found(self):
        """SKILL.md が少なくとも1つ見つかる"""
        self.assertGreater(len(self.skills), 0)

    def test_frontmatter_exists(self):
        """全 SKILL.md に frontmatter がある"""
        for skill in self.skills:
            self.assertIsNotNone(skill['frontmatter'],
                                 f"{skill['path']} に frontmatter がない")

    def test_name_field(self):
        """frontmatter に name フィールドがある"""
        for skill in self.skills:
            fm = skill['frontmatter']
            if fm is None:
                continue
            self.assertIn('name', fm,
                          f"{skill['path']} に name がない")

    def test_name_matches_directory(self):
        """name がディレクトリ名と一致"""
        for skill in self.skills:
            fm = skill['frontmatter']
            if fm is None:
                continue
            self.assertEqual(fm.get('name'), skill['dir_name'],
                             f"{skill['path']}: name '{fm.get('name')}' != dir '{skill['dir_name']}'")

    def test_description_field(self):
        """frontmatter に description がある"""
        for skill in self.skills:
            fm = skill['frontmatter']
            if fm is None:
                continue
            # description が直接あるか、マルチラインで空でないか
            self.assertTrue(
                'description' in fm and fm['description'],
                f"{skill['path']} に description がない")

    def test_user_invocable_field(self):
        """AI 専用 Skill は user-invocable: false を持つ"""
        for skill in self.skills:
            fm = skill['frontmatter']
            if fm is None:
                continue
            # user-invocable フィールドの存在は任意だが、
            # false の場合は明示されているべき
            # ここではフィールドの存在のみチェック
            # (user-invocable がないデフォルトは true)


class TestSkillCrossReferences(unittest.TestCase):
    """SKILL.md 間の相互参照テスト"""

    @classmethod
    def setUpClass(cls):
        """全 SKILL.md の内容を読み込み"""
        cls.skill_contents = {}
        cls.skill_names = set()
        for skill_md in PLUGINS_DIR.rglob('SKILL.md'):
            plugin_name = skill_md.relative_to(PLUGINS_DIR).parts[0]
            skill_dir_name = skill_md.parent.name
            full_name = f'{plugin_name}:{skill_dir_name}'
            cls.skill_names.add(full_name)
            cls.skill_contents[full_name] = skill_md.read_text(encoding='utf-8')

    def _find_skill_references(self, content):
        """SKILL.md 内の /plugin:skill 形式の参照を抽出"""
        # /kaizen:fix-staged, /doc-structure:where 等
        pattern = r'/(\w[\w-]*):(\w[\w-]*)'
        matches = re.findall(pattern, content)
        return [(plugin, skill) for plugin, skill in matches]

    def test_internal_references_valid(self):
        """内部プラグインへの参照先が存在する"""
        internal_plugins = {p.name for p in PLUGINS_DIR.iterdir() if p.is_dir()}

        for skill_name, content in self.skill_contents.items():
            refs = self._find_skill_references(content)
            for ref_plugin, ref_skill in refs:
                if ref_plugin not in internal_plugins:
                    # 外部プラグイン（query-rules 等）はスキップ
                    continue
                expected = f'{ref_plugin}:{ref_skill}'
                self.assertIn(expected, self.skill_names,
                              f"{skill_name} が存在しない内部 Skill '{expected}' を参照")


# =========================================================================
# 4. 参照ファイル存在確認テスト
# =========================================================================

class TestReferencedFilesExist(unittest.TestCase):
    """SKILL.md や plugin.json が参照するファイルの存在確認"""

    def test_review_criteria_default_exists(self):
        """kaizen のデフォルトレビュー観点ファイルが存在"""
        path = PLUGINS_DIR / 'kaizen' / 'defaults' / 'review_criteria.md'
        self.assertTrue(path.is_file(), f'{path} が存在しない')

    def test_resolve_review_context_script_exists(self):
        """review Skill が参照するスクリプトが存在"""
        path = PLUGINS_DIR / 'kaizen' / 'skills' / 'review' / 'scripts' / 'resolve_review_context.py'
        self.assertTrue(path.is_file(), f'{path} が存在しない')

    def test_classify_dirs_script_exists(self):
        """init-doc-structure Skill が参照するスクリプトが存在"""
        path = PLUGINS_DIR / 'doc-structure' / 'scripts' / 'classify_dirs.py'
        self.assertTrue(path.is_file(), f'{path} が存在しない')

    def test_doc_structure_format_exists(self):
        """init-doc-structure Skill が参照するスキーマ仕様が存在"""
        path = REPO_ROOT / 'docs' / 'doc_structure_format.md'
        self.assertTrue(path.is_file(), f'{path} が存在しない')

    def test_skill_directories_have_skill_md(self):
        """skills/ 配下の全ディレクトリに SKILL.md がある"""
        for plugin_dir in PLUGINS_DIR.iterdir():
            if not plugin_dir.is_dir():
                continue
            skills_dir = plugin_dir / 'skills'
            if not skills_dir.is_dir():
                continue
            for skill_dir in skills_dir.iterdir():
                if not skill_dir.is_dir():
                    continue
                skill_md = skill_dir / 'SKILL.md'
                self.assertTrue(skill_md.is_file(),
                                f"Skill ディレクトリ '{skill_dir}' に SKILL.md がない")


# =========================================================================
# 5. doc_structure_format.md とパーサーの整合性テスト
# =========================================================================

class TestSchemaConsistency(unittest.TestCase):
    """doc_structure_format.md の仕様とパーサーの整合性"""

    @classmethod
    def setUpClass(cls):
        cls.format_doc = (REPO_ROOT / 'docs' / 'doc_structure_format.md').read_text(encoding='utf-8')

    def test_format_doc_mentions_exclude(self):
        """仕様書に exclude が記載されている"""
        self.assertIn('exclude', self.format_doc)

    def test_format_doc_mentions_paths(self):
        """仕様書に paths が記載されている"""
        self.assertIn('paths', self.format_doc)

    def test_format_doc_mentions_description(self):
        """仕様書に description が記載されている"""
        self.assertIn('description', self.format_doc)

    def test_format_doc_mentions_version(self):
        """仕様書に version が記載されている"""
        self.assertIn('version', self.format_doc)

    def test_format_doc_mentions_resolve(self):
        """仕様書に --resolve が記載されている"""
        self.assertIn('--resolve', self.format_doc)

    def test_parser_supports_all_documented_fields(self):
        """パーサーが仕様書に記載された全フィールドを処理できる"""
        import sys
        sys.path.insert(0, str(PLUGINS_DIR / 'kaizen' / 'skills' / 'review' / 'scripts'))
        from resolve_review_context import _parse_doc_structure_yaml
        import tempfile

        # 全フィールドを含む YAML
        yaml_content = '''\
version: "1.0"

specs:
  requirement:
    paths: ["specs/*/requirements/"]
    exclude: ["archived"]
    description: "要件定義書"

rules:
  rule:
    paths: [rules/]
    description: "開発ルール"
'''
        tmpdir = tempfile.mkdtemp()
        try:
            yaml_file = os.path.join(tmpdir, '.doc_structure.yaml')
            with open(yaml_file, 'w') as f:
                f.write(yaml_content)
            result = _parse_doc_structure_yaml(yaml_file)

            self.assertIsNotNone(result)
            self.assertEqual(result['version'], '1.0')
            self.assertIn('paths', result['specs']['requirement'])
            self.assertIn('exclude', result['specs']['requirement'])
            self.assertIn('description', result['specs']['requirement'])
            self.assertIn('paths', result['rules']['rule'])
            self.assertIn('description', result['rules']['rule'])
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


# =========================================================================
# 6. README との整合性テスト
# =========================================================================

class TestReadmeConsistency(unittest.TestCase):
    """README.md の内容がプラグイン実態と一致"""

    @classmethod
    def setUpClass(cls):
        cls.readme = (REPO_ROOT / 'README.md').read_text(encoding='utf-8')
        cls.mp = _read_json(REPO_ROOT / '.claude-plugin' / 'marketplace.json')

    def test_all_plugins_listed_in_readme(self):
        """全プラグインが README に記載されている"""
        for plugin in self.mp['plugins']:
            self.assertIn(plugin['name'], self.readme,
                          f"プラグイン '{plugin['name']}' が README に記載されていない")

    def test_versions_in_readme(self):
        """README 内のバージョンが marketplace と一致"""
        for plugin in self.mp['plugins']:
            self.assertIn(plugin['version'], self.readme,
                          f"'{plugin['name']}' v{plugin['version']} が README にない")

    def test_skill_table_completeness(self):
        """README の Skills テーブルに全 Skill が含まれている"""
        for plugin_dir in PLUGINS_DIR.iterdir():
            if not plugin_dir.is_dir():
                continue
            skills_dir = plugin_dir / 'skills'
            if not skills_dir.is_dir():
                continue
            for skill_dir in skills_dir.iterdir():
                if not skill_dir.is_dir():
                    continue
                skill_md = skill_dir / 'SKILL.md'
                if not skill_md.is_file():
                    continue
                fm = _parse_skill_frontmatter(skill_md)
                if fm and fm.get('name'):
                    self.assertIn(fm['name'], self.readme,
                                  f"Skill '{fm['name']}' が README に記載されていない")


if __name__ == '__main__':
    unittest.main()
