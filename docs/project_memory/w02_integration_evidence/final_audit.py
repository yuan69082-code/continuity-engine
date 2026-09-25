"""Read-only W02 integration audit; write each final evidence file once.

This does not stage or modify Git state. Generated outputs list their own paths
without impossible self-referential hashes.
"""
import ast
import hashlib
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys
from urllib.parse import unquote


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'src'))
COLLECT = runpy.run_path(str(ROOT / 'docs/project_memory/w02_c_evidence/audit.py'))['collect']
from continuity_engine.testing.persistence import tree_inventory_hash  # noqa: E402
BASELINE = json.loads((HERE / 'baseline.json').read_text(encoding='utf-8'))
LABELS = ('integration-targeted-01', 'w02-abc-compat-01',
          'public-compat-01', 'full-final-01')
GENERATED = tuple('docs/project_memory/w02_integration_evidence/' + name
                  for name in ('final.audit.json', 'final.files.json', 'final.pending-files.md'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def status():
    raw = subprocess.check_output(['git', '-c', 'core.quotepath=false',
                                   'status', '--porcelain=v1', '-z', '--untracked-files=all'], cwd=ROOT)
    rows = {}
    for item in raw.split(b'\0'):
        if item:
            code, name = item[:2].decode('ascii'), item[3:].decode('utf-8')
            if code in ('R ', ' R', 'C ', ' C'):
                raise RuntimeError('RENAMED_OR_COPIED_PATH_REQUIRES_REVIEW')
            rows[name] = code
    return rows


def markdown_links(names, future):
    missing = []
    pattern = re.compile(r'(?<!!)\[[^\]]+\]\(([^)]+)\)')
    for name in names:
        if not name.endswith('.md'):
            continue
        source = ROOT / name
        for target in pattern.findall(source.read_text(encoding='utf-8')):
            path = target.strip().strip('<>').split('#', 1)[0]
            if not path or '://' in path or path.startswith(('mailto:', '#')):
                continue
            resolved = (source.parent / unquote(path)).resolve()
            if not resolved.exists() and resolved not in future:
                missing.append({'source': name, 'target': target})
    return missing


def main():
    current = COLLECT()
    rows = status()
    source_before, source_after = BASELINE['source'], current['source']
    source_changed = {p: {'before': source_before.get(p), 'after': source_after.get(p)}
                      for p in sorted(set(source_before) | set(source_after))
                      if source_before.get(p) != source_after.get(p)}
    expected_source_delta = {
        'src/continuity_engine/services/continuity_core_service.py',
        'tests/test_w02_integration.py',
    }
    excluded = BASELINE['excluded']
    excluded_delta = {p: {'before': value, 'after': sha(ROOT / p) if (ROOT / p).is_file() else None}
                      for p, value in excluded.items()
                      if not (ROOT / p).is_file() or sha(ROOT / p) != value}
    # Generated summaries are listed by path to avoid self-referential hashes.
    included = sorted(set(rows) - set(excluded) - set(GENERATED))
    unexpected_included = [name for name in included if name not in expected_source_delta
                           and name not in {'README.md', 'docs/project_memory/01_当前状态.md',
                                            'docs/project_memory/03_施工日志.md',
                                            'docs/project_memory/06_未完成事项.md',
                                            'docs/project_memory/10_档案修订记录.md',
                                            'docs/project_memory/13_P00_档案与测试索引.md',
                                            'docs/project_memory/CHANGELOG.md'}
                           and not name.startswith('docs/project_memory/w02_integration_evidence/')]
    runs = {}
    for label in LABELS:
        path = HERE / (label + '.json')
        if not path.is_file():
            runs[label] = {'missing': True}
            continue
        value = json.loads(path.read_text(encoding='utf-8'))
        stderr = (HERE / (label + '.stderr.log')).read_text(encoding='utf-8')
        match = re.search(r'Ran (\d+) tests? in', stderr)
        runs[label] = {
            'count': int(match.group(1)) if match else None,
            'exit_code': value['exit_code'], 'elapsed_seconds': value['elapsed_seconds'],
            'source_before': value['source_fingerprint_before'],
            'source_after': value['source_fingerprint_after'],
            'stable': value['source_inventory_identical'],
            'formal_identical': value['formal_identical'],
            'protected_identical': value['protected_identical'],
            'excluded_identical': value['excluded_identical'],
            'ok_summary': '\nOK' in stderr and 'FAILED (' not in stderr,
        }
    parse_errors = []
    for name in sorted(source_after):
        if name.endswith('.py'):
            try:
                ast.parse((ROOT / name).read_text(encoding='utf-8'), filename=name)
            except Exception as error:
                parse_errors.append({'path': name, 'type': type(error).__name__})
    diff = subprocess.run(['git', 'diff', '--check'], cwd=ROOT, capture_output=True,
                          text=True, encoding='utf-8', errors='replace', check=False)
    future = {(ROOT / path).resolve() for path in GENERATED}
    links = markdown_links(included, future)
    secret_pattern = re.compile(r'(?:sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})')
    secret_hits = [name for name in included if name.endswith(('.md', '.py'))
                   and secret_pattern.search((ROOT / name).read_text(encoding='utf-8'))]
    audit = {
        'branch': current['branch'], 'head': current['head'],
        'local_origin': current['localOrigin'], 'origin': current['origin'],
        'staged': current['staged'], 'tracked': current['tracked'],
        'source_count': len(source_after), 'source_fingerprint': current['sourceHash'],
        'source_delta_from_accepted_c': source_changed,
        'expected_source_delta_only': set(source_changed) == expected_source_delta,
        'run_results': runs,
        'runs_fixed_source': all(r.get('exit_code') == 0 and r.get('ok_summary')
            and r.get('source_before') == current['sourceHash']
            and r.get('source_after') == current['sourceHash'] and r.get('stable')
            and r.get('formal_identical') and r.get('protected_identical')
            and r.get('excluded_identical') for r in runs.values()),
        'protected_identical': current['protected'] == BASELINE['protected'],
        'planning_identical': {
            p: sha(ROOT / 'docs/project_memory/w01_planning_v15_20260923/planning' / p)
            for p in BASELINE['planning']
        } == BASELINE['planning'],
        'formal_identical': current['formal_files'] == BASELINE['formal_files'],
        'formal_count': len(current['formal_files']),
        'formal_tree_inventory_hash': tree_inventory_hash(ROOT / '.continuity-data'),
        'excluded_count': len(excluded), 'excluded_delta': excluded_delta,
        'unexpected_included': unexpected_included,
        'source_parse_errors': parse_errors, 'markdown_missing_links': links,
        'possible_secret_hits_in_new_code_docs': secret_hits,
        'git_diff_check_exit': diff.returncode,
        'git_diff_check_output': diff.stdout + diff.stderr,
        'included_count_before_generated': len(included),
        'generated_outputs': list(GENERATED),
    }
    gates = (audit['branch'] == 'main' and audit['head'] == BASELINE['head']
             and not audit['staged'] and audit['expected_source_delta_only']
             and audit['runs_fixed_source'] and audit['protected_identical']
             and audit['planning_identical'] and audit['formal_identical']
             and audit['formal_count'] == 7
             and audit['formal_tree_inventory_hash'] == BASELINE['formal_tree_inventory_hash']
             and not excluded_delta
             and not unexpected_included and not parse_errors and not links
             and not secret_hits and diff.returncode == 0)
    audit['ready_for_independent_review'] = bool(gates)
    if not gates:
        print(json.dumps(audit, ensure_ascii=False, indent=2))
        raise RuntimeError('W02_INTEGRATION_AUDIT_FAILED')
    files = {
        'source_fingerprint': current['sourceHash'],
        'included': {name: sha(ROOT / name) for name in included},
        'excluded': {name: sha(ROOT / name) for name in sorted(excluded)},
        'statuses': {name: rows[name] for name in sorted(rows)},
        'generated_outputs': list(GENERATED),
    }
    with (HERE / 'final.audit.json').open('w', encoding='utf-8') as stream:
        json.dump(audit, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    with (HERE / 'final.files.json').open('w', encoding='utf-8') as stream:
        json.dump(files, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    with (HERE / 'final.pending-files.md').open('w', encoding='utf-8') as stream:
        stream.write('# W02 整体贯通精确成果与原样排除清单\n\n')
        stream.write('本轮没有 Git 暂存、提交或推送授权。末尾三个审计输出因自引用只列路径。\n\n')
        stream.write(f'新增/修改成果 {len(included) + len(GENERATED)} 项；原样排除 {len(excluded)} 项。\n\n')
        stream.write('## 本轮成果\n\n')
        for name in (*included, *GENERATED):
            stream.write(f'- `{name}`\n')
        stream.write('\n## 原样排除\n\n')
        for name in sorted(excluded):
            stream.write(f'- `{name}`\n')
    print(json.dumps({'ready_for_independent_review': gates,
                      'source_fingerprint': current['sourceHash'],
                      'included_count': len(included) + len(GENERATED),
                      'excluded_count': len(excluded), 'runs': runs}, ensure_ascii=False))


if __name__ == '__main__':
    main()
