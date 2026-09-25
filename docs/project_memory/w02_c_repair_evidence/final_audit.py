"""Exclusive, read-only W02-C repair identity/link and pending-file audit."""
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PRIOR = ROOT / 'docs/project_memory/w02_c_evidence'
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(PRIOR))
from audit import collect
from continuity_engine.testing.persistence import tree_inventory_hash


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def status_paths():
    raw = subprocess.check_output(
        ['git', '-c', 'core.quotepath=false', 'status', '--porcelain=v1', '-z', '--untracked-files=all'],
        cwd=ROOT)
    rows = {}
    for item in raw.split(b'\x00'):
        if item:
            code, path = item[:2].decode('ascii'), item[3:].decode('utf-8')
            if code in ('R ', ' R', 'C ', ' C'):
                raise RuntimeError('RENAMED_OR_COPIED_PATH_REQUIRES_MANUAL_REVIEW')
            rows[path] = code
    return rows


def markdown_links(paths, prospective):
    missing = []
    pattern = re.compile(r'(?<!!)\[[^\]]+\]\(([^)]+)\)')
    for name in paths:
        if not name.endswith('.md'):
            continue
        source = ROOT / name
        for target in pattern.findall(source.read_text(encoding='utf-8')):
            target = target.strip().strip('<>').split('#', 1)[0]
            if not target or '://' in target or target.startswith(('mailto:', '#')):
                continue
            resolved = (source.parent / unquote(target)).resolve()
            if not resolved.exists() and resolved not in prospective:
                missing.append({'source': name, 'target': target})
    return missing


def main():
    old = json.loads((PRIOR / 'final.files.json').read_text(encoding='utf-8'))
    baseline = json.loads((PRIOR / 'baseline.json').read_text(encoding='utf-8'))
    current = collect()
    rows = status_paths()
    excluded = old['excluded']
    included = sorted(set(rows) - set(excluded))
    excluded_delta = {}
    for name, expected in excluded.items():
        actual = sha(ROOT / name) if (ROOT / name).is_file() else None
        if actual != expected:
            excluded_delta[name] = {'expected': expected, 'actual': actual}
    old_missing = sorted(set(old['included']) - set(included))
    ast_errors = []
    for name in sorted(current['source']):
        if name.endswith('.py'):
            try:
                ast.parse((ROOT / name).read_text(encoding='utf-8'), filename=name)
            except Exception as error:
                ast_errors.append({'path': name, 'error_type': type(error).__name__})
    diff = subprocess.run(['git', 'diff', '--check'], cwd=ROOT, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', check=False)
    generated = [f'docs/project_memory/w02_c_repair_evidence/{name}'
                 for name in ('final.audit.json', 'final.files.json', 'final.pending-files.md')]
    prospective = {(ROOT / name).resolve() for name in generated}
    test_labels = ['formal-final-01', 'w02-ab-final-01', 'public-final-01', 'full-final-01']
    test_results = {label: json.loads((HERE / f'{label}.json').read_text(encoding='utf-8'))
                    for label in test_labels}
    result = {
        'branch': current['branch'], 'head': current['head'], 'staged': current['staged'],
        'source_count': len(current['source']), 'source_fingerprint': current['sourceHash'],
        'tests_same_fixed_source': all(
            value['exit_code'] == 0 and value['source_inventory_identical']
            and value['source_fingerprint_before'] == current['sourceHash']
            and value['source_fingerprint_after'] == current['sourceHash']
            for value in test_results.values()),
        'test_labels': {label: {'exit_code': value['exit_code'], 'elapsed_seconds': value['elapsed_seconds']}
                        for label, value in test_results.items()},
        'protected_identical': baseline['protected'] == current['protected'],
        'formal_identical': baseline['formal_files'] == current['formal_files'],
        'formal_count': len(current['formal_files']),
        'formal_files_map_hash': current['formal_hash'],
        'formal_tree_inventory_hash': tree_inventory_hash(ROOT / '.continuity-data'),
        'planning_index_identical': baseline['indexHash'] == current['indexHash'],
        'excluded_expected': len(excluded), 'excluded_actual': len(set(rows) & set(excluded)),
        'excluded_delta': excluded_delta, 'old_w02c_included_missing': old_missing,
        'ast_errors': ast_errors, 'markdown_missing_links': markdown_links(included, prospective),
        'git_diff_check_exit': diff.returncode, 'git_diff_check_output': diff.stdout + diff.stderr,
        'included_before_generated_outputs': len(included),
    }
    files = {
        'source_fingerprint': current['sourceHash'],
        'included': {name: sha(ROOT / name) for name in included},
        'excluded': {name: sha(ROOT / name) for name in sorted(set(rows) & set(excluded))},
        'statuses': {name: rows[name] for name in sorted(rows)},
        'generated_outputs': generated,
    }
    for filename, value in (('final.audit.json', result), ('final.files.json', files)):
        with (HERE / filename).open('x', encoding='utf-8') as output:
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.write('\n')
    with (HERE / 'final.pending-files.md').open('x', encoding='utf-8') as output:
        output.write('# W02-C 补修后精确成果与保留清单\n\n')
        output.write('仅记录当前工作区待交付文件；不构成暂存或提交授权。')
        output.write('末尾三个审计输出因自引用无法包含自身 hash。\n\n')
        output.write(f'待交付成果 {len(included) + len(generated)} 项；原样排除 {len(files["excluded"])} 项。\n\n')
        output.write('## 待交付成果\n\n')
        for name in [*included, *generated]:
            output.write(f'- `{name}`\n')
        output.write('\n## 原样排除材料\n\n')
        for name in files['excluded']:
            output.write(f'- `{name}`\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
