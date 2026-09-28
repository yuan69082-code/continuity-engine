"""Capture W04-3 baseline; never run Engine, tests, or Git writes."""
import datetime, hashlib, json, pathlib, re, runpy, subprocess
ROOT = pathlib.Path(__file__).resolve().parents[3]
HERE = pathlib.Path(__file__).resolve().parent
def git(*args):
    return subprocess.check_output(['git','-c','core.quotepath=false',*args],cwd=ROOT,text=True,encoding='utf8').strip()
def save(name, value):
    (HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
if __name__ == '__main__':
    assert not (HERE/'baseline.json').exists()
    snap=runpy.run_path(str(ROOT/'docs/project_memory/w02_b_evidence/snapshot.py'))
    old=json.loads((ROOT/'docs/project_memory/w04_2_acceptance_evidence/baseline.json').read_text(encoding='utf8'))
    source=snap['source'](); fingerprint=snap['fingerprint'](source)
    assert fingerprint=='sha256:bee6fabd77fcdad99521ddaefdb1bf9166bc0b908b418e485fa998eb5fed53b5'
    assert git('rev-parse','HEAD')=='f64fb797ae4defae2dfd16278f38e89c8b13cd66'
    assert not git('diff','--name-only') and not git('diff','--cached','--name-only')
    retained=old['retained']; files=set(git('ls-files','--others','--exclude-standard').splitlines())
    assert {p for p in files if not p.startswith('docs/project_memory/w04_3_evidence/')}==set(retained)
    for p,h in retained.items(): assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
    save('baseline.json',dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),head=git('rev-parse','HEAD'),branch=git('branch','--show-current'),source=source,fingerprint=fingerprint,retained=retained,protected=old['protected'],planning=old['planning'],prior_test_identity_file='docs/project_memory/w04_2_completion_evidence/frozen-source-01.json',tracked_baseline={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in git('ls-files').splitlines() if (ROOT/p).is_file()}))
    (HERE/'run.py').write_bytes((ROOT/'docs/project_memory/w04_2_completion_evidence/run.py').read_bytes())
    note='''<!-- W04_3_AUTHORIZED_D090 -->
## D-090：W04 第三子批次开工授权

2026-09-28，用户授权N14工具发现与临时接入及N21查询能力衔接的实现、隔离测试和档案。W04-3=IN_PROGRESS，W04整体IN_PROGRESS；W04-1/D-087、W04-2/D-089及此前验收保持。仅TEST替身，不接真实服务/设备/凭据，不验收、不暂存/提交/push、不启动W04-4。

[Stage Brief](w04_3_evidence/stage-brief.md) · [逐项矩阵](w04_3_evidence/matrix.md) · [开工身份](w04_3_evidence/baseline.json)。旧记录原样保留。F1/H1/F2 UNKNOWN、SKIP及原失败不改写；现无已确认PLANNING_CONFLICT，EVIDENCE_CONFLICT待本批验证与独立复核。

'''
    decision=ROOT/'docs/project_memory/04_决策记录.md'
    assert not re.search(rb'## D-090',decision.read_bytes())
    for name in ('04_决策记录.md','03_施工日志.md','01_当前状态.md','06_未完成事项.md'):
        p=ROOT/'docs/project_memory'/name;p.write_bytes(note.encode('utf8')+p.read_bytes())
    print('baseline captured; D-090 kickoff only; no source/test changes')
