"""Read-only Engine audit; outputs new evidence files only, never Git writes."""
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
S = runpy.run_path(str(ROOT / 'docs/project_memory/w02_b_evidence/snapshot.py'))
SHARED = ['docs/project_memory/'+x for x in ('01_当前状态.md','03_施工日志.md','04_决策记录.md',
    '06_未完成事项.md','10_档案修订记录.md','工程总档案.md')]
IMPLEMENTATION = ['src/continuity_engine/domain/action_planning.py',
    'src/continuity_engine/domain/device_operation.py',
    'src/continuity_engine/services/device_operation_service.py',
    'src/continuity_engine/services/execution_service.py',
    'src/continuity_engine/services/execution_context_source.py',
    'src/continuity_engine/testing/w04_device_fixture.py', 'tests/test_w04_2_simulation.py']


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git(*args):
    return subprocess.run(['git','-c','core.quotepath=false',*args], cwd=ROOT,
                          capture_output=True, encoding='utf-8')


def main(label):
    destinations = [HERE / (label + x) for x in ('.audit.json', '.pending-files.md', '.git-status.txt', '.diff-check.txt')]
    if any(p.exists() for p in destinations):
        raise SystemExit('audit label exists; preserve it')
    audit, pending, statusfile, difffile = destinations
    baseline = json.loads((HERE/'baseline.json').read_text(encoding='utf-8'))
    frozen = json.loads((HERE/'frozen-source.json').read_text(encoding='utf-8'))
    src = S['source']()
    protected = baseline['protected']
    status = git('status','--short','--untracked-files=all')
    statusfile.write_text(status.stdout+status.stderr, encoding='utf-8')
    diff = git('diff','--check')
    difffile.write_text('exit_code='+str(diff.returncode)+'\nSTDOUT\n'+diff.stdout+'\nSTDERR\n'+diff.stderr,encoding='utf-8')
    paths = sorted(set(SHARED + IMPLEMENTATION + [p.relative_to(ROOT).as_posix() for p in HERE.iterdir()
        if p.is_file()] + [p.relative_to(ROOT).as_posix() for p in destinations]))
    working = set(git('ls-files','-m','-o','--exclude-standard').stdout.splitlines())
    historical = {}
    texts = {}
    for p in paths:
        if p.endswith('.md') and (ROOT/p).exists():
            text = (ROOT/p).read_text(encoding='utf-8')
            if p in SHARED:
                old = git('show',baseline['head']+':'+p).stdout
                historical[p] = text.replace('\r\n','\n').endswith(old.replace('\r\n','\n'))
                text = text[:-len(old)] if old and text.endswith(old) else text.split('<!-- W04_2_START_D088 -->')[0]
            texts[p] = text
    links = []
    for p,text in texts.items():
        for link in re.findall(r'\]\(([^)]+)\)',text):
            target = unquote(link.split('#',1)[0].strip('<>'))
            if target and not target.startswith(('https:','http:','mailto:')):
                if not (ROOT/p).parent.joinpath(target).exists() and (ROOT/p).parent.joinpath(target) not in destinations:
                    links.append([p,target])
    syntax=[]
    for p in src:
        if p.endswith('.py'):
            try: ast.parse((ROOT/p).read_text(encoding='utf-8'),filename=p)
            except (SyntaxError,UnicodeError) as exc: syntax.append([p,type(exc).__name__])
    sensitive=[]; unwanted=[]
    pattern = re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{35,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')
    for p in paths:
        if any(part in {'__pycache__','node_modules','build','dist','.venv','Temp','Sandbox'} for part in Path(p).parts) or Path(p).suffix in {'.pyc','.whl','.zip'}:
            unwanted.append(p)
        if (ROOT/p).exists() and pattern.search((ROOT/p).read_text(encoding='utf-8',errors='replace')):
            sensitive.append(p)
    pending.write_text('# W04-2 精确成果清单（未暂存）\n\n本批实现/测试/证据/必要档案；70份既有保留材料不在下表，逐项hash见 baseline.json。'+
        '六份共享档案只新增本批记录，既有D-085及历史内容保持。\n\n| 相对路径 | SHA-256 |\n|---|---|\n'+
        '\n'.join('| `'+p+'` | `'+sha(ROOT/p)+'` |' for p in paths if (ROOT/p).exists() and ROOT/p not in {audit,pending})+
        '\n\n审计和本清单也属于交付；审计记录本清单hash，自身hash由后续只读工具计算，不作自引用。\n',encoding='utf-8')
    data = dict(kind='w04_2_final_audit',at_utc=datetime.now(timezone.utc).isoformat(),
        head=git('rev-parse','HEAD').stdout.strip(),branch=git('branch','--show-current').stdout.strip(),
        local_origin_main=git('rev-parse','origin/main').stdout.strip(),staged=git('diff','--cached','--name-only').stdout.splitlines(),
        source_count=len(src),source_fingerprint=S['fingerprint'](src),source_matches_frozen=src==frozen['source'],
        original_test_files_unchanged=all(src.get(p)==h for p,h in baseline['source'].items() if p.startswith('tests/')),
        protected_mismatches={k:[p for p,h in values.items() if sha(ROOT/p)!=h] for k,values in protected.items()},
        planning_mismatches=[r['archivePath'] for r in baseline['planning'] if sha(ROOT/r['archivePath'])!=r['archiveSha256']],
        retained_count=len(baseline['retained']),retained_mismatch=[p for p,h in baseline['retained'].items() if sha(ROOT/p)!=h],
        historical_shared_tails_unchanged=historical,syntax_errors=syntax,missing_new_links=links,
        high_confidence_secret_findings=sensitive,unwanted_artifacts=unwanted,
        diff_check_exit=diff.returncode,diff_check_stdout=diff.stdout,diff_check_stderr=diff.stderr,
        delivery_count=len(paths),delivery_paths=paths,
        delivery_hashes_excluding_audit={p:sha(ROOT/p) for p in paths if (ROOT/p).exists() and ROOT/p!=audit},
        unexpected_working_paths=sorted(working-set(paths)-set(baseline['retained'])),
        missing_working_paths=sorted(set(paths)-working-{p.relative_to(ROOT).as_posix() for p in destinations}),
        git_writes=False,engine_or_tests_run_by_this_audit=False)
    audit.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:data[k] for k in ('source_count','source_fingerprint','source_matches_frozen','protected_mismatches',
        'retained_mismatch','historical_shared_tails_unchanged','syntax_errors','missing_new_links','unexpected_working_paths',
        'delivery_count','high_confidence_secret_findings')},ensure_ascii=False))


if __name__ == '__main__':
    main(sys.argv[1])
