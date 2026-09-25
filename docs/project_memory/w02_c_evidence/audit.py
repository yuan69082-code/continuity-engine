"""Read-only W02-C workspace identity collector; explicit output names never overwrite."""
import datetime
import json
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SNAPSHOT = runpy.run_path(str(ROOT / 'docs/project_memory/w02_b_evidence/snapshot.py'))


def collect():
    value = SNAPSHOT['collect']()
    data_root = ROOT / '.continuity-data'
    value['formal_files'] = {p.relative_to(data_root).as_posix(): SNAPSHOT['sha'](p)
                             for p in sorted(data_root.rglob('*')) if p.is_file()}
    value['formal_hash'] = SNAPSHOT['fingerprint'](value['formal_files'])
    value['at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return value


if __name__ == '__main__':
    path = HERE / (sys.argv[1] + '.json')
    with path.open('x', encoding='utf-8') as stream:
        json.dump(collect(), stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(path)
