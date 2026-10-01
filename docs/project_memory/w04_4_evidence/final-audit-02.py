"""Audit the second frozen version, preserving first-version audit tool/results."""
from pathlib import Path
here=Path(__file__).resolve().parent
source=(here/'final-audit.py').read_text(encoding='utf8').replace('-final-01','-final-02')
source=source.replace('remote-readonly-20261001.json','remote-readonly-final-02.json')
source=source.replace("checks['worktree_scope']=not unexpected", """checks['worktree_scope']=not unexpected
first_failure=json.loads((HERE/'full-final-01-failure-preservation.json').read_text(encoding='utf8'))
checks['first_full_failure_preserved']=all(sha(HERE/p)==h for p,h in first_failure['raw_hashes'].items())""")
exec(compile(source,str(here/'final-audit.py'),'exec'))
