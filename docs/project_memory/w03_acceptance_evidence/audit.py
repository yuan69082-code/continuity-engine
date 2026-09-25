"""Build a precise W03 acceptance manifest without modifying source or history."""
import hashlib
import json
import runpy
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = json.loads((ROOT / 'docs/project_memory/w03_evidence/baseline.json').read_text(encoding='utf-8'))
REPAIR = json.loads((ROOT / 'docs/project_memory/w03_n06_repair_evidence/final.audit.json').read_text(encoding='utf-8'))
COLLECT = runpy.run_path(str(ROOT / 'docs/project_memory/w02_c_evidence/audit.py'))['collect']
EXPECTED_HEAD = 'ec9c59054a599d028e39a80134abec6aa9802eba'
EXPECTED_SOURCE = 'sha256:d6a98e0ea091984c235cc16cd03c249f05b2c56e00ff2a423b9f95f774a23ecf'
ACCEPTANCE_DOCS = {
    'README.md',
    'docs/project_memory/05_已完成模块.md',
    'docs/project_memory/CHANGELOG.md',
}
EDITED_HISTORY_DOCS = {
    'docs/project_memory/01_当前状态.md',
    'docs/project_memory/03_施工日志.md',
    'docs/project_memory/04_决策记录.md',
    'docs/project_memory/06_未完成事项.md',
    'docs/project_memory/10_档案修订记录.md',
    'docs/project_memory/工程总档案.md',
    'docs/project_memory/w03_evidence/matrix.md',
}
SELF = {
    'docs/project_memory/w03_acceptance_evidence/final.audit.json',
    'docs/project_memory/w03_acceptance_evidence/final.pending-files.md',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


current = COLLECT()
if (current['branch'], current['head'], current['localOrigin']) != ('main', EXPECTED_HEAD, EXPECTED_HEAD):
    raise SystemExit('W03_ACCEPTANCE_GIT_BASELINE_CHANGED')
if current['staged']:
    raise SystemExit('W03_ACCEPTANCE_STAGE_NOT_EMPTY')
if (len(current['source']), current['sourceHash']) != (304, EXPECTED_SOURCE):
    raise SystemExit('W03_ACCEPTANCE_SOURCE_IDENTITY_CHANGED')
if (current['protected'] != BASE['protected'] or current['formal_files'] != BASE['formal_files']
        or current['formal_hash'] != BASE['formal_hash'] or current['plans'] != BASE['plans']
        or current['excluded'] != BASE['excluded']):
    raise SystemExit('W03_ACCEPTANCE_PROTECTION_CHANGED')

raw = subprocess.check_output(['git', '-c', 'core.quotepath=false', 'status',
                               '--porcelain=v1', '--untracked-files=all', '-z'], cwd=ROOT)
status = {}
for token in raw.split(b'\0'):
    if not token:
        continue
    if token[:2] in {b'R ', b' R', b'C ', b' C'}:
        raise SystemExit('W03_ACCEPTANCE_RENAME_OR_COPY_UNEXPECTED')
    path = token[3:].decode('utf-8').replace('\\', '/')
    if path in status:
        raise SystemExit('W03_ACCEPTANCE_DUPLICATE_PATH')
    status[path] = token[:2].decode('ascii')

prior = {entry['path']: entry['sha256'] for entry in REPAIR['deliverables']}
for path in REPAIR['generated_self_paths']:
    prior[path] = sha(ROOT / path)
if len(prior) != 270:
    raise SystemExit('W03_ACCEPTANCE_PRIOR_MANIFEST_COUNT_CHANGED')
if not set(prior).issubset(status):
    raise SystemExit('W03_ACCEPTANCE_PRIOR_RESULT_MISSING')
if sum(path in status for path in BASE['excluded']) != 57:
    raise SystemExit('W03_ACCEPTANCE_EXCLUSION_MISSING')
for path, old_hash in prior.items():
    if path not in EDITED_HISTORY_DOCS and sha(ROOT / path) != old_hash:
        raise SystemExit('W03_ACCEPTANCE_PRIOR_RESULT_CHANGED: ' + path)

additional = set(status) - set(prior) - set(BASE['excluded']) - SELF
allowed = ACCEPTANCE_DOCS | {
    'docs/project_memory/w03_acceptance_evidence/audit.py',
    'docs/project_memory/w03_acceptance_evidence/acceptance-report.md',
    'docs/project_memory/w03_acceptance_evidence/acceptance-matrix.md',
    'docs/project_memory/w03_acceptance_evidence/audit-helper-before-01.stdout.log',
    'docs/project_memory/w03_acceptance_evidence/audit-helper-before-01.stderr.log',
}
if additional != allowed:
    raise SystemExit('W03_ACCEPTANCE_UNEXPLAINED_INCREMENT: '
                     + repr(sorted(additional.symmetric_difference(allowed))))

paths = sorted(set(prior) | additional | SELF)
if set(paths) & set(BASE['excluded']):
    raise SystemExit('W03_ACCEPTANCE_EXCLUSION_IN_MANIFEST')
deliverables = [{'path': path, 'status': status.get(path, '??'),
                 'sha256': None if path in SELF else sha(ROOT / path)} for path in paths]
result = {
    'at': datetime.now(timezone.utc).isoformat(),
    'branch': current['branch'], 'head': current['head'],
    'local_origin': current['localOrigin'], 'origin': current['origin'],
    'source_count': len(current['source']), 'source_hash': current['sourceHash'],
    'protected_unchanged': True, 'formal_files_unchanged': True,
    'formal_hash_unchanged': True, 'plans_unchanged': True,
    'excluded_unchanged': True, 'excluded_count': len(BASE['excluded']),
    'excluded_in_status': sum(path in status for path in BASE['excluded']),
    'previous_deliverable_count': len(prior),
    'acceptance_increment': sorted(additional),
    'document_updates_within_previous_manifest': sorted(EDITED_HISTORY_DOCS),
    'deliverable_count': len(paths), 'deliverables': deliverables,
    'self_hash_omitted': sorted(SELF),
}
(HERE / 'final.audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',
                                       encoding='utf-8')
lines = [
    '# W03 正式验收最终精确提交清单', '',
    f"原 W03 累计成果 {len(prior)} 项；本次新增验收文件 {len(additional)} 项；最终 {len(paths)} 项。",
    f"源码/测试/资源 {len(current['source'])} 项，指纹 `{current['sourceHash']}`。",
    f"原 {len(BASE['excluded'])} 项排除材料不在本清单内，仍需原样保留。", '',
    '| 状态 | 路径 | SHA-256 |', '| --- | --- | --- |',
]
lines.extend(f"| `{row['status']}` | `{row['path']}` | `{row['sha256'] or 'SELF'}` |"
             for row in deliverables)
lines += ['', 'SELF 表示两份终局自引用清单，本表不列自身 hash；其余路径逐文件给出工作区 SHA-256。', '']
(HERE / 'final.pending-files.md').write_text('\n'.join(lines), encoding='utf-8')
print(json.dumps({key: result[key] for key in (
    'branch', 'head', 'source_count', 'source_hash', 'previous_deliverable_count',
    'acceptance_increment', 'deliverable_count', 'excluded_count', 'excluded_in_status')},
    ensure_ascii=False))
