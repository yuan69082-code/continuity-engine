"""New final version after evidenced fixes; one named group, never automatic retry."""
import datetime,json,os,pathlib,runpy,subprocess,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[3];HERE=pathlib.Path(__file__).resolve().parent
os.chdir(ROOT);sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'tests')]
os.environ['PYTHONDONTWRITEBYTECODE']='1';os.environ['PYTHONUTF8']='1'
snapshot=runpy.run_path(str(ROOT/'docs/project_memory/w02_b_evidence/snapshot.py'))
def identities(suite):
    for test in suite:
        if isinstance(test,unittest.TestSuite):yield from identities(test)
        else:yield test.id()
path=HERE/'frozen-source-final-02.json';mode=sys.argv[1]
source=snapshot['source']();fingerprint=snapshot['fingerprint'](source)
if mode=='freeze':
    base=json.loads((HERE/'baseline.json').read_text(encoding='utf8'))
    prior=json.loads((HERE/'frozen-source-final-01.json').read_text(encoding='utf8'))
    tests=sorted(identities(unittest.defaultTestLoader.discover('tests')))
    changed=[p for p,h in base['source'].items() if p.startswith('tests/') and source.get(p)!=h]
    assert not changed and not set(base['test_ids'])-set(tests)
    assert not set(prior['test_ids'])-set(tests)
    groups={k.replace('-01','-02'):v for k,v in prior['groups'].items()}
    groups['public-final-02']=json.loads((HERE/'public-scope-addendum-01.json').read_text(encoding='utf8'))['modules']
    value=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source=source,
        fingerprint=fingerprint,count=len(source),test_ids=tests,original_test_count=len(base['test_ids']),
        new_tests=sorted(set(tests)-set(base['test_ids'])),original_test_files_changed=changed,groups=groups,
        previous_final='frozen-source-final-01.json',reason='Two proven B-reply timeouts; native current path metadata and narrow provenance-copy repair',
        changes_since_previous={p:h for p,h in source.items() if prior['source'].get(p)!=h})
    with path.open('x',encoding='utf8') as out:json.dump(value,out,ensure_ascii=False,indent=2)
    print(json.dumps(dict(source_count=len(source),fingerprint=fingerprint,tests=len(tests),new=len(value['new_tests']),changed_paths=list(value['changes_since_previous']))))
else:
    frozen=json.loads(path.read_text(encoding='utf8'));assert frozen['source']==source
    raise SystemExit(subprocess.call([sys.executable,str(HERE/'run.py'),mode,
        '-m','unittest','-v',*frozen['groups'][mode]],cwd=ROOT))
