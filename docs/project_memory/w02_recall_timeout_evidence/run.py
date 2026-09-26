"""Write each isolated validation result once, including unsuccessful runs."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "docs/project_memory/w02_b_evidence"))
from snapshot import fingerprint, source  # noqa: E402


def write_new(path: Path, data: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(data)


def main() -> int:
    if len(sys.argv) < 3:
        raise SystemExit("usage: run.py LABEL command ...")
    label, command = sys.argv[1], sys.argv[2:]
    if not label.replace("-", "").replace("_", "").isalnum():
        raise SystemExit("invalid evidence label")
    paths = [HERE / (label + extension) for extension in (".json", ".stdout.log", ".stderr.log")]
    if any(p.exists() for p in paths):
        raise SystemExit("evidence label already exists")
    before = source()
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    tick = time.monotonic()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1",
               PYTHONPATH=os.pathsep.join((str(ROOT / "src"), str(ROOT))))
    try:
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=3600)
        code, stdout, stderr, interrupt = result.returncode, result.stdout, result.stderr, None
    except subprocess.TimeoutExpired as exc:
        code = None
        stdout, stderr, interrupt = exc.stdout or b"", exc.stderr or b"", "subprocess timeout"
    after = source()
    ended = dt.datetime.now(dt.timezone.utc).isoformat()
    write_new(paths[1], stdout)
    write_new(paths[2], stderr)
    record = dict(label=label, command=command, cwd=str(ROOT), started_at=started,
                  ended_at=ended, elapsed_seconds=round(time.monotonic() - tick, 3),
                  exit_code=code, interrupt=interrupt,
                  source_before=fingerprint(before), source_after=fingerprint(after),
                  source_unchanged=before == after,
                  stdout_sha256=hashlib.sha256(stdout).hexdigest(),
                  stderr_sha256=hashlib.sha256(stderr).hexdigest())
    write_new(paths[0], (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps(record, ensure_ascii=False))
    return 0 if code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
