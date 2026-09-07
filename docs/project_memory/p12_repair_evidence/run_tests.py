"""One recorded invocation; independent evidence survives fixture cleanup."""
import json
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from datetime import datetime, timezone


def main():
    directory = Path(__file__).resolve().parent
    root = directory.parents[2]
    label, *arguments = sys.argv[1:]
    if not re.fullmatch(r"[a-z0-9-]+", label) or not arguments:
        raise ValueError("provide a unique evidence label and Python arguments")
    paths = [directory / (label + suffix) for suffix in
             (".json", ".stdout.log", ".stderr.log")]
    if any(path.exists() for path in paths):
        raise FileExistsError("evidence labels cannot be reused")
    record = {"command": [sys.executable, *arguments], "cwd": str(root),
              "startedAt": datetime.now(timezone.utc).isoformat(),
              "environment": {"PYTHONPATH": "src", "PYTHONDONTWRITEBYTECODE": "1"},
              "exitCode": None, "interrupted": False}
    record['sourceTest']={str(p.relative_to(root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
        for folder in ('src','tests') for p in sorted((root/folder).rglob('*'))
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    record['inputScripts']={str(Path(a).resolve()):hashlib.sha256(Path(a).read_bytes()).hexdigest()
        for a in arguments if a.endswith('.py') and Path(a).is_file()}
    paths[0].write_text(json.dumps(record, indent=2), encoding="utf-8")
    started = time.perf_counter()
    try:
        with paths[1].open("wb") as out, paths[2].open("wb") as err:
            result = subprocess.run(record["command"], cwd=root, stdout=out, stderr=err,
                                    env={**os.environ, "PYTHONPATH": str(root / "src"),
                                         "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"})
            record["exitCode"] = result.returncode
    except BaseException as exc:
        record["interrupted"] = True
        record["harnessError"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        record["finishedAt"] = datetime.now(timezone.utc).isoformat()
        record["wallSeconds"] = round(time.perf_counter() - started, 3)
        paths[0].write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k:v for k,v in record.items() if k not in ('sourceTest','inputScripts')}), flush=True)
        print(paths[2].read_text(encoding="utf-8", errors="replace"), flush=True)
    return record["exitCode"]


if __name__ == "__main__":
    raise SystemExit(main())
