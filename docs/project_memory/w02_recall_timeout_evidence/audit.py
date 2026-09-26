"""Read-only boundary audit and exact delivery list; writes only new evidence files."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
BASE = json.loads((ROOT / 'docs/project_memory/w03_evidence/baseline.json').read_text(encoding='utf-8'))
SNAPSHOT = runpy.run_path(str(ROOT / 'docs/project_memory/w02_c_evidence/audit.py'))
os.environ['GIT_OPTIONAL_LOCKS'] = '0'


def git(*args: str) -> bytes:
    return subprocess.check_output(['git', '-c', 'core.quotepath=false', *args], cwd=ROOT)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_new(path: Path, data: bytes) -> None:
    with path.open('xb') as stream:
        stream.write(data)


def main() -> None:
    if sys.argv[1:] == ['--recheck-after-encoding-error']:
        outputs = ('verified-final.pending-files.md', 'verified-final.files.json', 'verified-final.audit.json')
    elif sys.argv[1:]:
        raise SystemExit('unsupported audit mode')
    else:
        outputs = ('final.pending-files.md', 'final.files.json', 'final.audit.json')
    if any((HERE / name).exists() for name in outputs):
        raise SystemExit('final audit output already exists; preserve it')
    now = SNAPSHOT['collect']()
    full = json.loads((HERE / 'full-final-01.json').read_text(encoding='utf-8'))
    tracked = {name for name in git('diff', '--name-only', '-z').decode('utf-8').split('\0') if name}
    untracked = {name for name in git('ls-files', '--others', '--exclude-standard', '-z').decode('utf-8').split('\0') if name}
    excluded = set(BASE['excluded'])
    approved_tracked = {
        'src/continuity_engine/services/associative_recall_service.py',
        'src/continuity_engine/storage/json_integration_repository.py',
        'docs/project_memory/01_当前状态.md',
        'docs/project_memory/03_施工日志.md',
        'docs/project_memory/06_未完成事项.md',
        'docs/project_memory/CHANGELOG.md',
    }
    unknown = sorted((tracked - approved_tracked) |
                     {p for p in untracked - excluded if not
                      (p.startswith('docs/project_memory/w02_recall_timeout_evidence/') or
                       p == 'tests/test_w02_recall_timeout.py')})
    paths = sorted((tracked | untracked) - excluded |
                   {f'docs/project_memory/w02_recall_timeout_evidence/{name}' for name in outputs})
    if unknown or tracked != approved_tracked:
        raise SystemExit(json.dumps({'unknown': unknown, 'tracked_difference': sorted(tracked ^ approved_tracked)}))
    protected_ok = now['protected'] == BASE['protected']
    excluded_ok = now['excluded'] == BASE['excluded']
    formal_ok = now['formal_files'] == BASE['formal_files'] and now['formal_hash'] == BASE['formal_hash']
    source_ok = full['source_before'] == full['source_after'] == now['sourceHash']
    if not all((protected_ok, excluded_ok, formal_ok, source_ok)):
        raise SystemExit(json.dumps({'protected_ok': protected_ok, 'excluded_ok': excluded_ok,
                                     'formal_ok': formal_ok, 'source_ok': source_ok}))
    links = []
    for relative in paths:
        if not relative.endswith('.md') or relative.endswith('final.pending-files.md'):
            continue
        path = ROOT / relative
        text = path.read_text(encoding='utf-8')
        if relative in approved_tracked:
            text = text.split('\n---\n', 1)[0]
        for raw in re.findall(r'\]\(([^)]+)\)', text):
            if raw.startswith(('https:', 'http:', '#', 'mailto:')):
                continue
            target = raw.split('#', 1)[0]
            if target and not (path.parent / target).exists():
                links.append({'file': relative, 'target': raw})
    if links:
        raise SystemExit(json.dumps({'broken_links': links}, ensure_ascii=False))
    pending = ['# W02 回忆时限定点补修：精确待提交清单', '',
               f'当前清单共 {len(paths)} 项；57 项原排除材料不在清单内。未暂存、未提交、未推送。', '',
               '本轮自引用清单/审计产物单列，'
               '不为它们在自身内容中伪造最终 hash。其他文件逐项记录 SHA-256。', '']
    for relative in paths:
        if relative in {f'docs/project_memory/w02_recall_timeout_evidence/{name}' for name in outputs}:
            pending.append(f'- `{relative}` — 自引用清单/审计产物')
        else:
            pending.append(f'- `{relative}` — `{sha(ROOT / relative)}`')
    pending.extend(('', '## 排除材料', '',
                    f'原有 {len(excluded)} 项已逐项与开工基线核对，均未改变；'
                    '完整路径及原 hash 见 `docs/project_memory/w03_evidence/baseline.json` 的 `excluded`。', ''))
    write_new(HERE / outputs[0], ('\n'.join(pending) + '\n').encode('utf-8'))
    files = {relative: sha(ROOT / relative) for relative in paths
             if relative not in {f'docs/project_memory/w02_recall_timeout_evidence/{name}'
                                 for name in outputs[1:]}}
    write_new(HERE / outputs[1], (json.dumps({'paths': paths, 'hashed_files': files,
                                             'self_unhashed': list(outputs[1:])},
                                            ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    audit = dict(at=dt.datetime.now(dt.timezone.utc).isoformat(),
                 branch=now['branch'], head=now['head'], local_origin=now['localOrigin'],
                 source_count=len(now['source']), source_hash=now['sourceHash'],
                 full_result=full, protected_ok=protected_ok, protected_count=len(BASE['protected']['protected']),
                 plans_ok=now['protected']['plans'] == BASE['protected']['plans'],
                 formal_ok=formal_ok, formal_hash=now['formal_hash'], excluded_ok=excluded_ok,
                 excluded_count=len(excluded), staged=now['staged'], tracked=sorted(tracked),
                 delivery_count=len(paths), delivery_paths=paths, unknown=unknown,
                 broken_links=links, files_json_sha256=sha(HERE / outputs[1]),
                 git_diff_check=subprocess.run(['git', 'diff', '--check'], cwd=ROOT,
                                               capture_output=True, text=True,
                                               encoding='utf-8').returncode)
    write_new(HERE / outputs[2], (json.dumps(audit, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print(json.dumps({key: audit[key] for key in ('source_count', 'source_hash', 'protected_ok',
                                                 'plans_ok', 'formal_ok', 'excluded_ok',
                                                 'excluded_count', 'staged', 'delivery_count',
                                                 'unknown', 'broken_links', 'git_diff_check')},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
