"""Read-only verification of supplied full-run evidence and current test IDs."""
import hashlib
import itertools
import json
import re
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Documents\continuity-engine")
EVIDENCE = ROOT / "docs/project_memory/pre_p12_r05_r06_evidence"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.dont_write_bytecode = True

stable = json.loads((EVIDENCE / "stable-source.json").read_text(encoding="utf-8"))
run = json.loads((EVIDENCE / "final-full.json").read_text(encoding="utf-8"))
post = json.loads((EVIDENCE / "final-audit.json").read_text(encoding="utf-8"))
log = (EVIDENCE / "final-full.stderr.log").read_text(encoding="utf-8")

def normalize(identifier):
    return identifier.removeprefix("tests.")

def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield normalize(item.id())

loader = unittest.TestLoader()
# Match the supplied full command: discover directly from tests. The tests
# directory uses namespace-style imports rather than an __init__.py package.
identities = list(flatten(loader.discover(str(ROOT / "tests"))))
logged = {}
for line in log.splitlines():
    match = re.fullmatch(r"(\w+) \(([\w.]+)\) \.\.\. (ok|skipped .+)", line)
    if match:
        # Python versions differ in whether the parenthesized description
        # already contains the test method name.
        identifier = normalize(match[2] if match[2].endswith("." + match[1])
                               else match[2] + "." + match[1])
        if identifier in logged:
            raise AssertionError("Duplicate test identity in full-run evidence")
        logged[identifier] = match[3]

source_mismatches = [path for path, expected in stable["sourceTest"].items()
    if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != expected]
assert not loader.errors, loader.errors
assert len(identities) == len(set(identities)) == 894
assert set(identities) == set(logged) == set(map(normalize, stable["testIdentities"]))
assert not source_mismatches, source_mismatches
assert run["exitCode"] == 0 and run["interrupted"] is False
assert run["command"][1:] == ["-m", "unittest", "discover", "-s", "tests", "-v"]
assert Path(run["cwd"]) == ROOT
assert datetime.fromisoformat(stable["capturedAt"]) <= datetime.fromisoformat(run["startedAt"])
assert datetime.fromisoformat(run["startedAt"]) < datetime.fromisoformat(run["finishedAt"])
assert datetime.fromisoformat(run["finishedAt"]) <= datetime.fromisoformat(post["capturedAt"])
assert post["sourceStable"] is True

from continuity_engine.services.learning_service import LearningService

# This compares the refactored pure formula to the pre-existing mathematical
# policy. It does not replace the end-to-end invalid-support regression tests.
formula_checks = 0
for count in (3, 4):
    for values in itertools.product((0.0, 0.2, 0.45, 0.6, 0.75, 0.8, 0.95, 1.0), repeat=count):
        old = round(max(values[0], min(1.0, sum(values) / count + 0.1 * (count - 1))), 6)
        assert LearningService._validation_confidence(values[0], list(values)) == old
        formula_checks += 1

print(json.dumps({
    "evidenceVerification": "PASS",
    "fullRunWasIndependentlyReexecutedThisTurn": False,
    "currentTestIdentities": len(identities),
    "loggedFullRunPass": sum(status == "ok" for status in logged.values()),
    "loggedFullRunSkip": {name: status for name, status in logged.items() if status != "ok"},
    "sourceFilesVerified": len(stable["sourceTest"]),
    "sourceMismatches": source_mismatches,
    "loaderErrors": loader.errors,
    "snapshotRunAuditTimestampOrderValid": True,
    "unchangedConfidenceFormulaCases": formula_checks,
    "suppliedFullRun": run,
    "suppliedFullLogSHA256": hashlib.sha256((EVIDENCE / "final-full.stderr.log").read_bytes()).hexdigest(),
}, indent=2, ensure_ascii=False))
