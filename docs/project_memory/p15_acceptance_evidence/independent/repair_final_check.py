"""Final read-only workspace identity check after writing the planning report."""
import json
from run_review import base, OUT

previous = json.loads((OUT / 'repair-extra-probes-20260909-01.after.json').read_text(encoding='utf-8'))
current = base.snapshot()
result = {
    'engineFilesStillUnchanged': previous == current,
    'fileCount': len(current),
    'changed': sorted(p for p in set(previous) | set(current) if previous.get(p) != current.get(p)),
    'reportPresent': (OUT / 'repair-review-report-20260909.md').is_file(),
    'auxiliaryCheckErrorPreserved': {
        'attempt': 'An initial final-check one-liner imported snapshot directly from run_review.',
        'error': "ImportError: cannot import name 'snapshot' from 'run_review'",
        'cause': 'The existing harness exposes snapshot as base.snapshot, not as a top-level symbol.',
        'effect': 'No Engine code ran or changed; not an Engine defect or behavioral test failure.',
        'correction': 'This separate checker uses the actual base.snapshot entry point.',
    },
}
with (OUT / 'repair-final-check-20260909.json').open('x', encoding='utf-8') as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2)
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result['engineFilesStillUnchanged'] and result['reportPresent'] else 1)
