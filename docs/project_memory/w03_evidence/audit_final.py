"""Read-only W03 identity audit and exact workspace inventory."""
import hashlib
import json
import runpy
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
COLLECT = runpy.run_path(str(ROOT / 'docs/project_memory/w02_c_evidence/audit.py'))['collect']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    baseline = json.loads((HERE / 'baseline.json').read_text(encoding='utf-8'))
    current = COLLECT()
    remote = subprocess.run(['git', '-c', 'credential.interactive=never', 'ls-remote',
                             'origin', 'refs/heads/main'], cwd=ROOT,
                            capture_output=True, timeout=15)
    remote_sha = remote.stdout.decode('ascii', errors='ignore').split()[0] if remote.returncode == 0 and remote.stdout else None
    remote_status = ('OK' if remote_sha else
                     'SEC_E_NO_CREDENTIALS' if b'SEC_E_NO_CREDENTIALS' in remote.stderr else
                     'UNAVAILABLE')
    raw = subprocess.run(['git', '-c', 'core.quotepath=false', 'status',
                          '--porcelain=v1', '--untracked-files=all', '-z'],
                         cwd=ROOT, capture_output=True, check=True).stdout
    changes = []
    for token in raw.split(b'\0'):
        if not token:
            continue
        path = token[3:].decode('utf-8').replace('\\', '/')
        # A rename would need an extra -z token; W03 has no rename authorization.
        if token[:2] in {b'R ', b' R', b'C ', b' C'}:
            raise SystemExit('unexpected rename/copy in W03 workspace')
        changes.append({'status': token[:2].decode('ascii'), 'path': path})
    excluded = baseline['excluded']
    excluded_status = [entry for entry in changes if entry['path'] in excluded]
    generated = {'docs/project_memory/w03_evidence/final.audit.json',
                 'docs/project_memory/w03_evidence/final.pending-files.md'}
    deliverables = [entry for entry in changes
                    if entry['path'] not in excluded and entry['path'] not in generated]
    for entry in deliverables:
        file = ROOT / entry['path']
        entry['sha256'] = sha(file) if file.is_file() else None
    result = {
        'at': datetime.now(timezone.utc).isoformat(),
        'branch': current['branch'], 'head': current['head'],
        'local_origin': current['localOrigin'], 'remote_url': current['origin'],
        'remote_main_sha': remote_sha, 'remote_query': remote_status,
        'source_count': len(current['source']), 'source_hash': current['sourceHash'],
        'source_changed_from_baseline': current['sourceHash'] != baseline['sourceHash'],
        'protected_unchanged': current['protected'] == baseline['protected'],
        'formal_files_unchanged': current['formal_files'] == baseline['formal_files'],
        'formal_hash_unchanged': current['formal_hash'] == baseline['formal_hash'],
        'plans_unchanged': current['plans'] == baseline['plans'],
        'excluded_unchanged': current['excluded'] == excluded,
        'excluded_count': len(excluded), 'excluded_in_status': len(excluded_status),
        'staged': current['staged'], 'tracked': current['tracked'],
        'deliverables': deliverables, 'generated_self_paths': sorted(generated),
    }
    (HERE / 'final.audit.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# W03 精确工作区成果清单', '',
             '此清单不是 Git 暂存授权。旧 57 项排除材料按开工清单逐文件 hash 原样保留。', '',
             f"源码/测试/资源 {result['source_count']} 项，指纹 `{result['source_hash']}`。",
             f"当前成果 {len(deliverables)+len(generated)} 项（含两项自引用清单文件）；暂存 `{result['staged']}`。", '',
             '| 工作区状态 | 路径 | SHA-256 |', '| --- | --- | --- |']
    for entry in deliverables:
        lines.append(f"| `{entry['status']}` | `{entry['path']}` | `{entry['sha256'] or 'MISSING'}` |")
    lines += ['', '自引用生成材料：`docs/project_memory/w03_evidence/final.audit.json`、'
              '`docs/project_memory/w03_evidence/final.pending-files.md`。其自身 hash 不在表内；'
              '运行审计脚本会重新生成。', '']
    (HERE / 'final.pending-files.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps({key: result[key] for key in ('source_count','source_hash',
        'protected_unchanged','formal_hash_unchanged','plans_unchanged',
        'excluded_unchanged','excluded_count','excluded_in_status','staged')},
        ensure_ascii=False))


if __name__ == '__main__':
    main()
