#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Directory classification script for .doc_structure.yaml generation.

Scans a project for markdown directories and classifies them as
rules or specs, then estimates doc_type for each directory.

Based on DocAdvisor's classify_dirs.py (standalone version without toc_utils dependency).

Usage:
    python3 classify_dirs.py [project_root]
    python3 classify_dirs.py [project_root] --format doc_structure
    python3 classify_dirs.py [project_root] --format summary
    python3 classify_dirs.py [project_root] --format yaml

Options:
    --format doc_structure  Output as .doc_structure.yaml content (default)
    --format yaml           YAML classification result with confidence
    --format summary        Human-readable summary

Created by: k_terada
"""

import sys
import re
import os
import argparse
from pathlib import Path


# Directories to always skip
SKIP_DIRS = {
    '.git', '.claude', '.github', '.vscode', '.idea',
    'node_modules', '__pycache__', '.tox', '.mypy_cache',
    'venv', '.venv', 'env', '.env',
    'dist', 'build', 'target', 'out',
    '.next', '.nuxt', '.svelte-kit',
    'vendor', 'Pods', '.gradle',
}

# Files that indicate a directory is not a documentation directory
SKIP_INDICATORS = {'package.json', 'Cargo.toml', 'go.mod', 'pom.xml', 'setup.py', 'pyproject.toml'}

# confidence 値の順序（数値が大きいほど高信頼度）
_CONFIDENCE_ORDER = {'low': 0, 'medium': 1, 'high': 2}

# Term indicators for category classification (rules vs specs)
RULE_TERMS = [
    r'\bmust\b', r'\bshall\b', r'\bshould not\b', r'\bmust not\b',
    r'\bconvention\b', r'\bstandard\b', r'\bguideline\b',
    r'\bprohibited\b', r'\bnaming\b', r'\bworkflow\b',
    r'\brule\b', r'\bpolicy\b', r'\bdo not\b', r'\bforbidden\b',
    r'\bcompliance\b', r'\bbest practice\b',
]

SPEC_TERMS = [
    r'\brequirement\b', r'\bdesign\b', r'\bfeature\b',
    r'\bspecification\b', r'\barchitecture\b', r'\bcomponent\b',
    r'\buse case\b', r'\bacceptance criteria\b', r'\buser story\b',
    r'\bfunctional\b', r'\bnon-functional\b', r'\binterface\b',
    r'\bapi\b', r'\bschema\b', r'\bdata model\b',
    r'\bsequence\b', r'\bstate\b', r'\bplan\b',
]

# Directory name to doc_type mapping
DOC_TYPE_NAMES = {
    'requirements': 'requirement', 'requirement': 'requirement', 'req': 'requirement', 'reqs': 'requirement',
    'designs': 'design', 'design': 'design', 'des': 'design',
    'plans': 'plan', 'plan': 'plan',
    'rules': 'rule', 'rule': 'rule',
    'workflows': 'workflow', 'workflow': 'workflow',
    'guides': 'guide', 'guide': 'guide',
    'references': 'reference', 'reference': 'reference', 'ref': 'reference',
    'api': 'api', 'apis': 'api',
    'specs': 'spec', 'spec': 'spec', 'specifications': 'spec',
    'standards': 'rule', 'conventions': 'rule',
    'policies': 'rule', 'guidelines': 'guide',
}


def get_project_root(path=None):
    """Find project root by looking for .git directory."""
    start = Path(path) if path else Path.cwd()
    current = start.resolve()
    while current != current.parent:
        if (current / '.git').exists():
            return str(current)
        current = current.parent
    return str(start.resolve())


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Classify project directories for .doc_structure.yaml'
    )
    parser.add_argument('project_root', nargs='?', default=None,
                        help='Project root directory (default: auto-detect from .git)')
    parser.add_argument('--format', choices=['doc_structure', 'yaml', 'summary'],
                        default='doc_structure',
                        help='Output format (default: doc_structure)')
    parser.add_argument('--skip', type=str, default='',
                        help='Comma-separated top-level directories to skip')
    return parser.parse_args()


def find_md_dirs(project_root):
    """
    Find directories containing .md files.

    Returns:
        list of (relative_dir_path, md_file_count)
    """
    results = []
    root = Path(project_root)

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        current = Path(dirpath)
        rel = current.relative_to(root)
        rel_str = str(rel)

        # Skip hidden and system directories (filter in-place to prevent descent)
        dirnames[:] = [
            d for d in dirnames
            if d not in SKIP_DIRS
            and not d.startswith('.')
        ]

        # Skip root directory itself
        if rel_str == '.':
            continue

        # Skip if directory contains project indicators (source code dir)
        if any((current / ind).exists() for ind in SKIP_INDICATORS):
            continue

        # Count .md files in this directory (not recursive)
        md_files = [f for f in filenames if f.endswith('.md')]
        if md_files:
            results.append((rel_str, len(md_files)))

    return results


def is_readme_only(project_root, dir_path):
    """Check if directory only contains README/CHANGELOG type files."""
    root = Path(project_root)
    dir_full = root / dir_path
    md_files = [f.name.lower() for f in dir_full.glob('*.md')]
    skip_names = {'readme.md', 'changelog.md', 'contributing.md', 'license.md',
                  'code_of_conduct.md', 'security.md'}
    return all(f in skip_names for f in md_files)


def extract_front_matter(filepath):
    """
    Extract front matter from a markdown file.

    Returns:
        dict or None
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read(4096)
    except (IOError, OSError):
        return None

    if not content.startswith('---'):
        return None

    end = content.find('---', 3)
    if end == -1:
        return None

    fm_content = content[3:end]
    result = {}
    for line in fm_content.split('\n'):
        line = line.strip()
        if ':' in line and not line.startswith('#'):
            key, _, val = line.partition(':')
            result[key.strip()] = val.strip().strip('"\'')

    return result


def classify_by_frontmatter(project_root, dir_path):
    """
    Classify directory by front matter doc_type.

    Returns:
        tuple: (category, confidence, reason) or None
    """
    root = Path(project_root)
    dir_full = root / dir_path

    md_files = list(dir_full.glob('*.md'))
    if not md_files:
        return None

    rules_count = 0
    specs_count = 0
    total_with_fm = 0

    for md_file in md_files:
        fm = extract_front_matter(md_file)
        if not fm or 'doc_type' not in fm:
            continue

        total_with_fm += 1
        doc_type = fm['doc_type'].lower()

        if doc_type in ('rule', 'rules', 'guideline', 'standard', 'workflow'):
            rules_count += 1
        elif doc_type in ('requirement', 'requirements', 'design', 'plan',
                          'specification', 'spec', 'specs'):
            specs_count += 1

    if total_with_fm == 0:
        return None

    total_classified = rules_count + specs_count
    if total_classified == 0:
        return None

    if rules_count > specs_count:
        confidence = 'high' if rules_count == total_with_fm else 'medium'
        return ('rules', confidence,
                f"frontmatter doc_type=rule ({rules_count}/{total_with_fm} files)")
    elif specs_count > rules_count:
        confidence = 'high' if specs_count == total_with_fm else 'medium'
        return ('specs', confidence,
                f"frontmatter doc_type=spec ({specs_count}/{total_with_fm} files)")
    else:
        return None


def classify_by_dirname(dir_path):
    """
    Classify directory by name heuristic.

    Returns:
        tuple: (category, confidence, reason) or None
    """
    rule_names = {'rules', 'rule', 'guidelines', 'standards', 'policies', 'conventions'}
    spec_names = {'specs', 'spec', 'specifications', 'requirements', 'design',
                  'designs', 'plans', 'features', 'proposals'}

    for part in Path(dir_path).parts:
        part_lower = part.lower()
        if part_lower in rule_names:
            return ('rules', 'medium', f"dirname match: {part_lower}")
        if part_lower in spec_names:
            return ('specs', 'medium', f"dirname match: {part_lower}")

    return None


def score_file_terms(filepath):
    """
    Score a file by rule/spec term frequency.

    Returns:
        tuple: (rule_score, spec_score)
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read().lower()
    except (IOError, OSError):
        return (0, 0)

    rule_score = 0
    for pattern in RULE_TERMS:
        rule_score += len(re.findall(pattern, content, re.IGNORECASE))

    spec_score = 0
    for pattern in SPEC_TERMS:
        spec_score += len(re.findall(pattern, content, re.IGNORECASE))

    return (rule_score, spec_score)


def classify_by_terms(project_root, dir_path):
    """
    Classify directory by term ranking.

    Returns:
        tuple: (category, confidence, reason) or None
    """
    root = Path(project_root)
    dir_full = root / dir_path

    md_files = list(dir_full.glob('*.md'))
    if not md_files:
        return None

    total_rule = 0
    total_spec = 0

    for md_file in md_files:
        r, s = score_file_terms(md_file)
        total_rule += r
        total_spec += s

    total = total_rule + total_spec
    if total == 0:
        return None

    ratio = max(total_rule, total_spec) / total if total > 0 else 0

    if ratio < 0.6:
        return None

    if total_rule > total_spec:
        confidence = 'high' if ratio >= 0.75 else 'medium'
        return ('rules', confidence,
                f"term_ranking: rule_score={total_rule}, spec_score={total_spec}")
    else:
        confidence = 'high' if ratio >= 0.75 else 'medium'
        return ('specs', confidence,
                f"term_ranking: rule_score={total_rule}, spec_score={total_spec}")


def classify_directory(project_root, dir_path):
    """
    Classify a single directory using multiple strategies.

    Priority:
    1. Front matter doc_type (highest)
    2. Directory name heuristic
    3. Term ranking (fallback)

    Returns:
        tuple: (category, confidence, reason) or None
    """
    result = classify_by_frontmatter(project_root, dir_path)
    if result:
        return result

    result = classify_by_dirname(dir_path)
    if result:
        return result

    result = classify_by_terms(project_root, dir_path)
    if result:
        return result

    return None


def estimate_doc_type(dir_path, category):
    """
    Estimate doc_type from directory path components.

    Returns:
        string: Estimated doc_type name (e.g., 'requirement', 'design', 'rule')
    """
    parts = Path(dir_path).parts

    # Check each path component against known doc_type names
    for part in reversed(parts):
        part_lower = part.lower()
        if part_lower in DOC_TYPE_NAMES:
            return DOC_TYPE_NAMES[part_lower]

    # Default based on category
    return 'rule' if category == 'rules' else 'spec'


def aggregate_to_top_dirs(classified_dirs):
    """
    Aggregate subdirectory classifications to top-level directories.

    doc_type が同一のサブディレクトリのみ集約する。
    異なる doc_type を持つサブディレクトリは個別パスを保持する。

    Returns:
        dict: {category: [{dir, confidence, reason, doc_type}]}
    """
    # Phase 1: 各エントリの doc_type を事前計算
    enriched = []
    for dir_path, category, confidence, reason in classified_dirs:
        doc_type = estimate_doc_type(dir_path, category)
        parts = Path(dir_path).parts
        top_dir = parts[0] if parts else dir_path
        enriched.append({
            'dir': dir_path, 'category': category,
            'confidence': confidence, 'reason': reason,
            'doc_type': doc_type, 'top_dir': top_dir,
        })

    # Phase 2: (category, top_dir, doc_type) でグループ化
    groups = {}
    for entry in enriched:
        key = (entry['category'], entry['top_dir'], entry['doc_type'])
        groups.setdefault(key, []).append(entry)

    # Phase 3: category 混在チェック
    top_dir_categories = {}
    for (category, top_dir, _), _ in groups.items():
        top_dir_categories.setdefault(top_dir, set()).add(category)

    result = {'rules': [], 'specs': [], 'skip': [], 'mixed': []}

    # Phase 4: グループごとに集約 or 個別パス
    for (category, top_dir, doc_type), entries in groups.items():
        is_mixed = len(top_dir_categories[top_dir]) > 1

        if is_mixed:
            # category 混在 → 個別パス保持
            for e in entries:
                result[category].append({
                    'dir': f"{e['dir']}/",
                    'confidence': e['confidence'],
                    'reason': e['reason'],
                    'doc_type': doc_type,
                })
        elif len(entries) > 1 or entries[0]['dir'] == top_dir:
            # 同一 doc_type 複数サブディレクトリ → top_dir に集約
            best_confidence = max(
                (e['confidence'] for e in entries),
                key=lambda c: _CONFIDENCE_ORDER.get(c, 0)
            )
            result[category].append({
                'dir': f"{top_dir}/",
                'confidence': best_confidence,
                'reason': f"aggregated from {len(entries)} subdirs: {entries[0]['reason']}",
                'doc_type': doc_type,
            })
        else:
            # 単一サブディレクトリ → 個別パス保持
            e = entries[0]
            result[category].append({
                'dir': f"{e['dir']}/",
                'confidence': e['confidence'],
                'reason': e['reason'],
                'doc_type': doc_type,
            })

    return result


def build_doc_structure(classification):
    """
    Build .doc_structure.yaml content from classification result.

    Groups directories by category and estimates doc_type for each.

    Returns:
        dict: {category: {doc_type: {paths: [...]}}}
    """
    structure = {}

    for category in ('specs', 'rules'):
        entries = classification.get(category, [])
        if not entries:
            continue

        doc_types = {}
        for entry in entries:
            dir_path = entry['dir']
            doc_type = entry.get('doc_type') or estimate_doc_type(dir_path, category)

            if doc_type not in doc_types:
                doc_types[doc_type] = {'paths': []}
            doc_types[doc_type]['paths'].append(dir_path)

        if doc_types:
            structure[category] = doc_types

    return structure


def output_doc_structure(classification):
    """Output as .doc_structure.yaml content."""
    structure = build_doc_structure(classification)

    print('version: "1.0"')

    for category in ('specs', 'rules'):
        if category not in structure:
            continue

        print(f"\n{category}:")
        for doc_type, info in structure[category].items():
            paths = info['paths']
            if len(paths) == 1:
                print(f"  {doc_type}:")
                print(f"    paths: [{paths[0]}]")
            else:
                print(f"  {doc_type}:")
                print(f"    paths:")
                for p in paths:
                    print(f"      - {p}")


def output_yaml(classification):
    """Output classification result as YAML with confidence."""
    print("classification:")

    for category in ('rules', 'specs'):
        entries = classification.get(category, [])
        print(f"  {category}:")
        if not entries:
            print("    []")
        else:
            for entry in entries:
                print(f"    - dir: {entry['dir']}")
                print(f"      confidence: {entry['confidence']}")
                print(f"      doc_type: {entry.get('doc_type') or estimate_doc_type(entry['dir'], category)}")
                print(f"      reason: \"{entry['reason']}\"")

    for category in ('skip', 'mixed'):
        entries = classification.get(category, [])
        if entries:
            print(f"  {category}:")
            for entry in entries:
                print(f"    - dir: {entry['dir']}")
                print(f"      reason: \"{entry.get('reason', '')}\"")


def output_summary(classification):
    """Output human-readable classification summary."""
    has_output = False

    for category in ('rules', 'specs'):
        entries = classification.get(category, [])
        if entries:
            print(f"  {category}:")
            for e in entries:
                dir_str = e['dir'].ljust(30)
                doc_type = e.get('doc_type') or estimate_doc_type(e['dir'], category)
                print(f"    {dir_str} type={doc_type} ({e['confidence']}: {e['reason']})")
            has_output = True

    skip_entries = classification.get('skip', [])
    if skip_entries:
        print(f"  skipped:")
        for e in skip_entries:
            dir_str = e['dir'].ljust(30)
            print(f"    {dir_str} ({e['reason']})")
        has_output = True

    if not has_output:
        print("  No document directories detected.")


def main():
    args = parse_args()

    project_root = get_project_root(args.project_root)

    # Find directories with .md files
    md_dirs = find_md_dirs(project_root)

    # Filter by --skip
    if args.skip:
        skip_prefixes = [s.strip().rstrip('/') for s in args.skip.split(',') if s.strip()]
        md_dirs = [(d, c) for d, c in md_dirs if not any(
            d == prefix or d.startswith(prefix + '/') for prefix in skip_prefixes
        )]

    if not md_dirs:
        if args.format == 'summary':
            print("  No document directories detected.")
        elif args.format == 'doc_structure':
            print('version: "1.0"')
            print("")
            print("# No document directories detected.")
            print("# Add your document paths manually.")
            print("# specs:")
            print("#   requirement:")
            print("#     paths: [specs/requirements/]")
        else:
            print("classification:")
            print("  rules: []")
            print("  specs: []")
        return 0

    # Classify each directory
    classified = []
    skip_entries = []

    for dir_path, md_count in md_dirs:
        # Skip README-only directories
        if is_readme_only(project_root, dir_path):
            skip_entries.append({
                'dir': f"{dir_path}/",
                'reason': 'README/CHANGELOG only',
            })
            continue

        result = classify_directory(project_root, dir_path)
        if result:
            category, confidence, reason = result
            classified.append((dir_path, category, confidence, reason))
        else:
            skip_entries.append({
                'dir': f"{dir_path}/",
                'reason': f'unclassifiable ({md_count} md files)',
            })

    # Aggregate subdirectories to top-level
    classification = aggregate_to_top_dirs(classified)
    classification['skip'] = skip_entries

    # Output
    if args.format == 'doc_structure':
        output_doc_structure(classification)
    elif args.format == 'summary':
        output_summary(classification)
    else:
        output_yaml(classification)

    return 0


if __name__ == '__main__':
    sys.exit(main())
