"""D-084 read-only boundary audit with one-time exact-list evidence outputs."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import runpy
import subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
REPAIR = ROOT / 'docs/project_memory/w02_recall_timeout_evidence'
BASE = json.loads((ROOT / 'docs/project_memory/w03_evidence/baseline.json').read_text(encoding='utf-8'))
REVIEWED = json.loads((REPAIR / 'verified-final.files.json').read_text(encoding='utf-8'))
REVIEW_AUDIT = json.loads((REPAIR / 'verified-final.audit.json').read_text(encoding='utf-8'))
SNAPSHOT = runpy.run_path(str(ROOT / 'docs/project_memory/w02_c_evidence/audit.py'))
EXPECTED_HEAD = '8c6e18cd30108f553df0bde55d7a190a114ea1a0'
EXPECTED_SOURCE = 'sha256:1008aabea9c72f769b97886cd9017051da083a95d14f9d9a010d7a738daa297b'
TRACKED = {
    'src/continuity_engine/services/associative_recall_service.py',
    'src/continuity_engine/storage/json_integration_repository.py',
    'docs/project_memory/01_当前状态.md',
    'docs/project_memory/03_施工日志.md',
    'docs/project_memory/04_决策记录.md',
    'docs/project_memory/05_已完成模块.md',
    'docs/project_memory/06_未完成事项.md',
    'docs/project_memory/CHANGELOG.md',
}
ACCEPTANCE_DIR = 'docs/project_memory/w02_recall_timeout_acceptance_evidence/'
OUTPUTS = ('final.pending-files.md', 'final.files.json', 'final.audit.json')
UPDATED_REVIEWED_DOCS = {
    'docs/project_memory/01_当前状态.md',
    'docs/project_memory/03_施工日志.md',
    'docs/project_memory/06_未完成事项.md',
    'docs/project_memory/CHANGELOG.md',
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> bytes:
    return subprocess.check_output(['git', '-c', 'core.quotepath=false', *args], cwd=ROOT)


def write_new(path: Path, data: bytes) -> None:
    with path.open('xb') as stream:
        stream.write(data)


def main() -> None:
    if any((HERE / name).exists() for name in OUTPUTS):
        raise SystemExit('D-084 output already exists; preserve original evidence')
    now = SNAPSHOT['collect']()
    tracked = {x for x in git('diff', '--name-only', '-z').decode('utf-8').split('\0') if x}
    untracked = {x for x in git('ls-files', '--others', '--exclude-standard', '-z').decode('utf-8').split('\0') if x}
    excluded = set(BASE['excluded'])
    outputs = {ACCEPTANCE_DIR + name for name in OUTPUTS}
    paths = sorted((tracked | untracked | outputs) - excluded)
    expected = set(REVIEWED['paths']) | {
        'docs/project_memory/04_决策记录.md',
        'docs/project_memory/05_已完成模块.md',
        ACCEPTANCE_DIR + 'acceptance-report.md',
        ACCEPTANCE_DIR + 'acceptance-matrix.md',
        ACCEPTANCE_DIR + 'audit.py',
    } | outputs
    unknown = sorted((tracked | untracked | outputs) - (expected | excluded))
    missing = sorted(expected - set(paths))
    reviewed_mismatches = sorted(
        path for path, digest in REVIEWED['hashed_files'].items()
        if path not in UPDATED_REVIEWED_DOCS and sha(ROOT / path) != digest
    )
    reviewed_originals_present = all((ROOT / p).exists() for p in REVIEWED['paths'])
    protected_ok = now['protected'] == BASE['protected']
    formal_ok = now['formal_files'] == BASE['formal_files'] and now['formal_hash'] == BASE['formal_hash']
    excluded_ok = now['excluded'] == BASE['excluded']
    source_ok = len(now['source']) == 305 and now['sourceHash'] == EXPECTED_SOURCE
    git_ok = (now['branch'] == 'main' and now['head'] == now['localOrigin'] == EXPECTED_HEAD
              and not now['staged'] and tracked == TRACKED)
    if not all((protected_ok, formal_ok, excluded_ok, source_ok, git_ok,
                reviewed_originals_present)) or unknown or missing or reviewed_mismatches:
        raise SystemExit(json.dumps({
            'protected_ok': protected_ok, 'formal_ok': formal_ok,
            'excluded_ok': excluded_ok, 'source_ok': source_ok,
            'git_ok': git_ok, 'reviewed_originals_present': reviewed_originals_present,
            'unknown': unknown, 'missing': missing,
            'reviewed_mismatches': reviewed_mismatches,
        }, ensure_ascii=False))
    links = []
    for relative in paths:
        if not relative.endswith('.md') or relative in outputs:
            continue
        path = ROOT / relative
        body = path.read_text(encoding='utf-8')
        if relative in TRACKED:
            body = body.split('\n---\n', 1)[0]
        for target in re.findall(r'\]\(([^)]+)\)', body):
            if target.startswith(('https:', 'http:', '#', 'mailto:')):
                continue
            local = target.split('#', 1)[0]
            resolved = (path.parent / local).resolve() if local else None
            if local and not resolved.exists() and resolved.relative_to(ROOT).as_posix() not in outputs:
                links.append({'file': relative, 'target': target})
    diff = subprocess.run(['git', 'diff', '--check'], cwd=ROOT, capture_output=True)
    if links or diff.returncode:
        raise SystemExit(json.dumps({'broken_links': links, 'git_diff_check': diff.returncode},
                                    ensure_ascii=False))
    pending = [
        '# D-084 W02 回忆时限补修：最终精确提交清单', '',
        f'本次逐路径清单共 {len(paths)} 项；原 57 项排除材料单列且不纳入。',
        '三个自引用终局产物只列路径，不在自身内容中伪造 hash；其他文件逐项给出 SHA-256。', '',
    ]
    for relative in paths:
        pending.append(f'- `{relative}` — ' +
                       ('自引用终局产物' if relative in outputs else f'`{sha(ROOT / relative)}`'))
    pending.extend(('', '## 排除材料', '',
                    '原 57 项路径和 hash 见 `docs/project_memory/w03_evidence/baseline.json`'
                    ' 的 `excluded`；本次终局审计逐项确认未变。', ''))
    write_new(HERE / OUTPUTS[0], ('\n'.join(pending) + '\n').encode('utf-8'))
    hashed = {relative: sha(ROOT / relative) for relative in paths
              if relative not in {ACCEPTANCE_DIR + OUTPUTS[1], ACCEPTANCE_DIR + OUTPUTS[2]}}
    files = {'paths': paths, 'hashed_files': hashed,
             'self_unhashed': [ACCEPTANCE_DIR + OUTPUTS[1], ACCEPTANCE_DIR + OUTPUTS[2]]}
    write_new(HERE / OUTPUTS[1], (json.dumps(files, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    audit = {
        'at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'decision': 'D-084', 'branch': now['branch'], 'head': now['head'],
        'local_origin': now['localOrigin'], 'source_count': len(now['source']),
        'source_hash': now['sourceHash'], 'protected_ok': protected_ok,
        'protected_count': len(BASE['protected']['protected']),
        'plans_ok': now['protected']['plans'] == BASE['protected']['plans'],
        'formal_ok': formal_ok, 'formal_hash': now['formal_hash'],
        'excluded_ok': excluded_ok, 'excluded_count': len(excluded),
        'staged': now['staged'], 'delivery_count': len(paths), 'delivery_paths': paths,
        'reviewed_105_preserved_except_acceptance_docs': not reviewed_mismatches,
        'reviewed_mismatches': reviewed_mismatches, 'unknown': unknown,
        'missing': missing, 'broken_links': links, 'git_diff_check': diff.returncode,
        'git_diff_check_warnings': diff.stderr.decode('utf-8', errors='replace').splitlines(),
        'pending_sha256': sha(HERE / OUTPUTS[0]),
        'files_json_sha256': sha(HERE / OUTPUTS[1]),
        'reviewed_files_json_sha256': sha(REPAIR / 'verified-final.files.json'),
        'reviewed_audit_sha256': sha(REPAIR / 'verified-final.audit.json'),
    }
    write_new(HERE / OUTPUTS[2], (json.dumps(audit, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({key: audit[key] for key in (
        'decision', 'source_count', 'source_hash', 'protected_ok', 'plans_ok',
        'formal_ok', 'excluded_ok', 'excluded_count', 'staged', 'delivery_count',
        'reviewed_mismatches', 'unknown', 'missing', 'broken_links', 'git_diff_check',
    )}, ensure_ascii=False))


if __name__ == '__main__':
    main()
