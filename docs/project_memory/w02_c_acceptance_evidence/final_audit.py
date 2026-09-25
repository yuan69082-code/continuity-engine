"""Read-only identity and precise-file audit for W02-C acceptance.

The three final outputs are written once after every prerequisite passes. They
are listed by path, without self-referential hashes in final.files.json.
"""

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
REPAIR = HERE.parent / 'w02_c_repair_evidence'
PRIOR = HERE.parent / 'w02_c_evidence'
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(PRIOR))
from audit import collect  # noqa: E402
from continuity_engine.testing.persistence import tree_inventory_hash  # noqa: E402


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def status_paths():
    raw = subprocess.check_output(
        ['git', '-c', 'core.quotepath=false', 'status', '--porcelain=v1', '-z', '--untracked-files=all'],
        cwd=ROOT,
    )
    rows = {}
    for item in raw.split(b'\0'):
        if not item:
            continue
        code, path = item[:2].decode('ascii'), item[3:].decode('utf-8')
        if code in ('R ', ' R', 'C ', ' C'):
            raise RuntimeError('RENAMED_OR_COPIED_PATH_REQUIRES_MANUAL_REVIEW')
        rows[path] = code
    return rows


def broken_links(paths, prospective):
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
    before = json.loads((REPAIR / 'final.files.json').read_text(encoding='utf-8'))
    baseline = json.loads((PRIOR / 'baseline.json').read_text(encoding='utf-8'))
    current = collect()
    rows = status_paths()
    changed_docs = {
        'README.md',
        'docs/project_memory/01_当前状态.md',
        'docs/project_memory/03_施工日志.md',
        'docs/project_memory/04_决策记录.md',
        'docs/project_memory/06_未完成事项.md',
        'docs/project_memory/10_档案修订记录.md',
        'docs/project_memory/13_P00_档案与测试索引.md',
        'docs/project_memory/CHANGELOG.md',
        'docs/project_memory/工程总档案.md',
    }
    added = {
        'docs/project_memory/05_已完成模块.md',
        'docs/project_memory/w02_c_acceptance_evidence/acceptance-report.md',
        'docs/project_memory/w02_c_acceptance_evidence/acceptance-matrix.md',
        'docs/project_memory/w02_c_acceptance_evidence/final_audit.py',
    }
    generated = [
        'docs/project_memory/w02_c_acceptance_evidence/' + name
        for name in ('final.audit.json', 'final.files.json', 'final.pending-files.md')
    ]
    previous = set(before['included']) | set(before['generated_outputs'])
    expected = previous | added | set(generated) | set(before['excluded'])
    actual = set(rows) | set(generated)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    included = sorted((set(rows) - set(before['excluded'])))
    unchanged_delta = {}
    for name, expected_hash in before['included'].items():
        if name in changed_docs:
            continue
        actual_hash = digest(ROOT / name) if (ROOT / name).is_file() else None
        if actual_hash != expected_hash:
            unchanged_delta[name] = {'expected': expected_hash, 'actual': actual_hash}
    excluded_delta = {}
    for name, expected_hash in before['excluded'].items():
        actual_hash = digest(ROOT / name) if (ROOT / name).is_file() else None
        if actual_hash != expected_hash:
            excluded_delta[name] = {'expected': expected_hash, 'actual': actual_hash}
    parse_errors = []
    for name in sorted(current['source']):
        if name.endswith('.py'):
            try:
                ast.parse((ROOT / name).read_text(encoding='utf-8'), filename=name)
            except Exception as error:
                parse_errors.append({'path': name, 'error_type': type(error).__name__})
    diff = subprocess.run(
        ['git', 'diff', '--check'], cwd=ROOT, capture_output=True, text=True,
        encoding='utf-8', errors='replace', check=False,
    )
    prospective = {(ROOT / name).resolve() for name in generated}
    links = broken_links(included, prospective)
    secret_pattern = re.compile(r'(?:sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})')
    secret_hits = [name for name in sorted(changed_docs | added)
                   if secret_pattern.search((ROOT / name).read_text(encoding='utf-8'))]
    test_labels = ('formal-final-01', 'w02-ab-final-01', 'public-final-01', 'full-final-01')
    tests = {label: json.loads((REPAIR / (label + '.json')).read_text(encoding='utf-8'))
             for label in test_labels}
    source_fixed = current['sourceHash'] == before['source_fingerprint'] and len(current['source']) == 296
    tests_fixed = all(
        result['exit_code'] == 0 and result['source_inventory_identical']
        and result['source_fingerprint_before'] == current['sourceHash']
        and result['source_fingerprint_after'] == current['sourceHash']
        for result in tests.values()
    )
    audit = {
        'branch': current['branch'], 'head': current['head'], 'staged': current['staged'],
        'source_count': len(current['source']), 'source_fingerprint': current['sourceHash'],
        'source_fixed': source_fixed, 'tests_same_fixed_source': tests_fixed,
        'test_labels': {label: {'exit_code': value['exit_code'], 'elapsed_seconds': value['elapsed_seconds']}
                        for label, value in tests.items()},
        'protected_identical': baseline['protected'] == current['protected'],
        'formal_identical': baseline['formal_files'] == current['formal_files'],
        'formal_count': len(current['formal_files']),
        'formal_tree_inventory_hash': tree_inventory_hash(ROOT / '.continuity-data'),
        'planning_index_identical': baseline['indexHash'] == current['indexHash'],
        'excluded_count': len(before['excluded']), 'excluded_delta': excluded_delta,
        'previous_included_unchanged_delta': unchanged_delta,
        'status_missing': missing, 'status_unexpected': unexpected,
        'ast_errors': parse_errors, 'markdown_missing_links': links,
        'new_document_secret_hits': secret_hits,
        'git_diff_check_exit': diff.returncode,
        'git_diff_check_output': diff.stdout + diff.stderr,
        'included_before_generated_outputs': len(included),
        'generated_outputs': generated,
    }
    gates = (
        current['branch'] == 'main' and current['head'] == 'd23441619f82c1b186736f5d65e2f9de34d95522'
        and not current['staged'] and source_fixed and tests_fixed
        and audit['protected_identical'] and audit['formal_identical']
        and audit['formal_count'] == 7 and audit['planning_index_identical']
        and not excluded_delta and not unchanged_delta and not missing and not unexpected
        and not parse_errors and not links and not secret_hits and diff.returncode == 0
    )
    audit['ready_for_precise_staging'] = bool(gates)
    if not gates:
        print(json.dumps(audit, ensure_ascii=False, indent=2))
        raise RuntimeError('ACCEPTANCE_AUDIT_FAILED')
    files = {
        'source_fingerprint': current['sourceHash'],
        'included': {name: digest(ROOT / name) for name in included},
        'excluded': {name: digest(ROOT / name) for name in sorted(before['excluded'])},
        'statuses': {name: rows[name] for name in sorted(rows)},
        'generated_outputs': generated,
    }
    with (HERE / 'final.audit.json').open('x', encoding='utf-8') as output:
        json.dump(audit, output, ensure_ascii=False, indent=2)
        output.write('\n')
    with (HERE / 'final.files.json').open('x', encoding='utf-8') as output:
        json.dump(files, output, ensure_ascii=False, indent=2)
        output.write('\n')
    with (HERE / 'final.pending-files.md').open('x', encoding='utf-8') as output:
        output.write('# W02-C 正式验收后逐文件提交与排除清单\n\n')
        output.write('仅以下成果获本轮用户授权提交；不使用全仓暂存。')
        output.write('末尾三个审计输出因自引用只列路径，不列自身 hash。\n\n')
        output.write(f'待提交 {len(included) + len(generated)} 项；排除且原样保留 {len(files["excluded"])} 项。\n\n')
        output.write('## 应提交\n\n')
        for name in [*included, *generated]:
            output.write(f'- `{name}`\n')
        output.write('\n## 原样排除\n\n')
        for name in files['excluded']:
            output.write(f'- `{name}`\n')
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == '__main__':
    main()
