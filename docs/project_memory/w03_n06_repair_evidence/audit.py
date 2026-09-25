"""Read-only source/protection audit; writes only this repair's new evidence files."""
import hashlib
import json
import runpy
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
BASE=json.loads((HERE.parent/'w03_evidence'/'baseline.json').read_text(encoding='utf-8'))
COLLECT=runpy.run_path(str(ROOT/'docs/project_memory/w02_c_evidence/audit.py'))['collect']
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

current=COLLECT()
raw=subprocess.check_output(['git','-c','core.quotepath=false','status',
    '--porcelain=v1','--untracked-files=all','-z'],cwd=ROOT)
changes=[]
for token in raw.split(b'\0'):
    if not token:continue
    if token[:2] in {b'R ',b' R',b'C ',b' C'}:raise SystemExit('rename/copy not authorized')
    path=token[3:].decode('utf-8').replace('\\','/')
    changes.append({'status':token[:2].decode('ascii'),'path':path})
excluded=BASE['excluded']
generated={'docs/project_memory/w03_n06_repair_evidence/final.audit.json',
           'docs/project_memory/w03_n06_repair_evidence/final.pending-files.md'}
deliverables=[]
for entry in changes:
    if entry['path'] in excluded or entry['path'] in generated:continue
    file=ROOT/entry['path']
    deliverables.append({**entry,'sha256':sha(file) if file.is_file() else None})
result={'at':datetime.now(timezone.utc).isoformat(),
    'branch':current['branch'],'head':current['head'],'local_origin':current['localOrigin'],
    'origin':current['origin'],'staged':current['staged'],'tracked':current['tracked'],
    'source_count':len(current['source']),'source_hash':current['sourceHash'],
    'protected_unchanged':current['protected']==BASE['protected'],
    'formal_files_unchanged':current['formal_files']==BASE['formal_files'],
    'formal_hash_unchanged':current['formal_hash']==BASE['formal_hash'],
    'plans_unchanged':current['plans']==BASE['plans'],
    'excluded_unchanged':current['excluded']==excluded,
    'excluded_count':len(excluded),'excluded_in_status':sum(x['path'] in excluded for x in changes),
    'deliverables':deliverables,'generated_self_paths':sorted(generated)}
(HERE/'final.audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=['# W03/N06 修补后精确成果清单','','这是工作区清单，不是 Git 暂存授权。',
       f"源码/测试/资源 {result['source_count']} 项；指纹 `{result['source_hash']}`。",
       f"成果 {len(deliverables)+len(generated)} 项（含两项自引用材料）；排除 {len(excluded)} 项，均保持原样。",'',
       '| 状态 | 路径 | SHA-256 |','| --- | --- | --- |']
lines.extend(f"| `{x['status']}` | `{x['path']}` | `{x['sha256'] or 'MISSING'}` |" for x in deliverables)
lines += ['', '自引用文件：`docs/project_memory/w03_n06_repair_evidence/final.audit.json`、'
          '`docs/project_memory/w03_n06_repair_evidence/final.pending-files.md`；其自身 hash 不列入表。','']
(HERE/'final.pending-files.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({key:result[key] for key in ('source_count','source_hash','protected_unchanged',
    'formal_hash_unchanged','plans_unchanged','excluded_unchanged','excluded_count',
    'excluded_in_status','staged')},ensure_ascii=False))
