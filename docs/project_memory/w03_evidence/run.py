"""Run one named W03 evidence set without replacing prior results."""
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
COLLECT = runpy.run_path(str(ROOT / "docs/project_memory/w02_c_evidence/audit.py"))["collect"]


def main():
    if len(sys.argv) < 3:
        raise SystemExit("usage: run.py LABEL unittest-arguments...")
    label = sys.argv[1]
    if not label.replace("-", "").replace("_", "").isalnum():
        raise SystemExit("invalid label")
    targets = [HERE / (label + suffix) for suffix in (".json", ".started.json", ".stdout.log", ".stderr.log")]
    if any(path.exists() for path in targets):
        raise SystemExit("label already exists")
    before = COLLECT()["sourceHash"]
    command = [sys.executable, "-m", "unittest", *sys.argv[2:]]
    started = datetime.now(timezone.utc).isoformat()
    targets[1].write_text(json.dumps({"started_at": started, "command": command,
                                       "source_before": before}, indent=2) + "\n", encoding="utf-8")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1",
               PYTHONPATH=str(ROOT / "src"))
    clock = time.monotonic()
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True)
    duration = time.monotonic() - clock
    targets[2].write_bytes(result.stdout)
    targets[3].write_bytes(result.stderr)
    after = COLLECT()["sourceHash"]
    targets[0].write_text(json.dumps({"started_at": started, "command": command,
                                      "exit_code": result.returncode, "elapsed_seconds": duration,
                                      "source_before": before, "source_after": after}, indent=2) + "\n",
                          encoding="utf-8")
    print(json.dumps({"label": label, "exit_code": result.returncode,
                      "elapsed_seconds": duration, "source_before": before,
                      "source_after": after}))
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
