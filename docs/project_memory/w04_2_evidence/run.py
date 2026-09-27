"""W04-2 isolated test evidence runner. Labels are immutable, never overwritten."""
from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SNAPSHOT = runpy.run_path(str(ROOT / "docs/project_memory/w02_b_evidence/snapshot.py"))


def run(label, tests):
    if not label or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for c in label):
        raise SystemExit("invalid label")
    paths = [HERE / (label + "." + suffix) for suffix in ("json", "stdout.log", "stderr.log")]
    if any(p.exists() for p in paths):
        raise SystemExit("label already used")
    command = [sys.executable, "-m", "unittest", *tests, "-v"]
    before = SNAPSHOT["fingerprint"](SNAPSHOT["source"]())
    start = time.perf_counter()
    record = {"label": label, "started_at": datetime.now(timezone.utc).isoformat(),
              "command": command, "cwd": str(ROOT), "source_before": before,
              "status": "STARTED"}
    paths[0].write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Historical tests import peer modules as top-level names. Preserve both
    # roots in the test launcher without changing any accepted test import.
    env = {**os.environ, "PYTHONPATH": os.pathsep.join((str(ROOT / "src"), str(ROOT / "tests"))),
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}
    with paths[1].open("x", encoding="utf-8") as out, paths[2].open("x", encoding="utf-8") as err:
        completed = subprocess.run(command, cwd=ROOT, env=env, stdout=out, stderr=err,
                                   timeout=3600, check=False)
    record.update(status="COMPLETED", exit_code=completed.returncode,
                  duration_seconds=round(time.perf_counter() - start, 3),
                  source_after=SNAPSHOT["fingerprint"](SNAPSHOT["source"]()))
    paths[0].write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False))
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit("usage: run.py LABEL TEST_MODULE_OR_CLASS ...")
    run(sys.argv[1], sys.argv[2:])
