"""One explicit frozen-version group. Never retries or starts the next group."""
import datetime,json,os,pathlib,runpy,subprocess,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[3]; HERE=pathlib.Path(__file__).resolve().parent
os.chdir(ROOT); sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'tests')]
SNAP=runpy.run_path(str(ROOT/'docs/project_memory/w02_b_evidence/snapshot.py'))
def ids(suite):
    for test in suite:
        if isinstance(test,unittest.TestSuite): yield from ids(test)
        else: yield test.id()
mode=sys.argv[1]; label=sys.argv[2] if len(sys.argv)>2 else 'final-01'
frozen_path=HERE/('frozen-source-'+label+'.json')
source=SNAP['source']()
if mode=='freeze':
    base=json.loads((HERE/'baseline.json').read_text(encoding='utf8'))
    old=json.loads((ROOT/'docs/project_memory/w04_4_evidence/frozen-source-final-02.json').read_text(encoding='utf8'))
    tests=sorted(ids(unittest.defaultTestLoader.discover('tests')))
    changed=[p for p,h in base['source'].items() if p.startswith('tests/') and source.get(p)!=h]
    assert not changed and not set(base['test_ids'])-set(tests)
    groups={'targeted': ['test_w04_package.W04PackageTests.test_discovery_history_body_and_native_cross_entry_share_authorities', 'test_w04_4_review_repairs'],
            'w04':old['groups']['w04-final-02']+['test_w04_4_review_repairs'],
            'public':old['groups']['public-final-02'],
            'full':old['groups']['full-final-02']+['test_w04_4_review_repairs']}
    counts={k:len(list(ids(unittest.defaultTestLoader.loadTestsFromNames(v)))) for k,v in groups.items()}
    value=dict(at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source=source,
        fingerprint=SNAP['fingerprint'](source),source_count=len(source),test_ids=tests,
        original_test_count=len(base['test_ids']),new_tests=sorted(set(tests)-set(base['test_ids'])),
        original_test_files_changed=changed,groups=groups,group_counts=counts)
    with frozen_path.open('x',encoding='utf8') as out:json.dump(value,out,ensure_ascii=False,indent=2)
    print(json.dumps({k:value[k] for k in ('fingerprint','source_count','original_test_count','group_counts')}))
else:
    frozen=json.loads(frozen_path.read_text(encoding='utf8')); assert source==frozen['source']
    raise SystemExit(subprocess.call([sys.executable,str(HERE/'run.py'),mode+'-'+label,
        '-m','unittest','-v',*frozen['groups'][mode]],cwd=ROOT))
