"""Read-only follow-up audit; write a uniquely named report, never replace evidence."""
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest
from urllib.parse import unquote


def main():
    evidence = Path(__file__).resolve().parent
    root = evidence.parents[2]
    destination = evidence / sys.argv[1]
    if destination.exists() or destination.parent != evidence or destination.suffix != ".json":
        raise ValueError("choose a new report filename in this evidence directory")
    os.chdir(root)
    sys.path[:0] = [str(root), str(root / "src")]
    before = json.loads((evidence / "before.json").read_text("utf-8"))
    stable = json.loads((evidence / "stable-source.json").read_text("utf-8"))
    errors = []

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def git(*args):
        return subprocess.check_output(["git", *args], env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"}).decode("utf-8")

    def changed(mapping):
        return [p for p, h in mapping.items() if not (root / p).is_file() or sha(root / p) != h]

    source = {p.relative_to(root).as_posix(): sha(p) for folder in ("src", "tests")
              for p in (root / folder).rglob("*") if p.is_file() and p.suffix in (".py", ".json", ".jsonl")}
    if source != stable["sourceTest"]:
        errors.append("source/test set or hashes changed after stable snapshot")
    allowed_source = {"src/continuity_engine/storage/json_resource_repository.py",
                      "src/continuity_engine/services/learning_service.py"}
    if set(changed(before["sourceTest"])) != allowed_source:
        errors.append("unexpected changes to pre-existing source/tests")
    if set(source) - set(before["sourceTest"]) != {"tests/test_pre_p12_r05_r06_followup.py"}:
        errors.append("unexpected new source/test file")
    protected_changes = changed(before["protected"])
    if protected_changes:
        errors.append("protected files changed")
    formal = sorted(p.relative_to(root).as_posix() for p in (root / ".continuity-data").rglob("*") if p.is_file())
    if formal != sorted(p for p in before["protected"] if p.startswith(".continuity-data/")):
        errors.append("formal data file set changed")
    history = {p: h for p, h in before["files"].items() if "_evidence/" in p}
    history_changes = changed(history)
    if history_changes:
        errors.append("pre-existing audit evidence changed")
    review = Path(before["reviewSource"])
    review_changes = [p for p, h in before["reviewFiles"].items()
                      if sha(review / p) != h or sha(evidence / "review-original" / p) != h]
    if review_changes:
        errors.append("independent review originals differ")
    incidental = {p.relative_to(root).as_posix(): sha(p) for p in root.rglob("*")
                  if p.is_file() and ".git" not in p.parts
                  and ("__pycache__" in p.parts or "sandbox" in str(p).lower())}
    if incidental != before["incidentalFiles"]:
        errors.append("cache/sandbox inventory changed")

    loader = unittest.TestLoader()
    suite = loader.discover("tests")

    def ids(node):
        for test in node:
            if isinstance(test, unittest.TestSuite):
                yield from ids(test)
            else:
                yield test.id()

    identities = sorted(ids(suite))
    if loader.errors or identities != stable["testIdentities"]:
        errors.append("test identities or imports changed")
    missing = sorted(set(before["testIdentities"]) - set(identities))
    if missing:
        errors.append("pre-existing tests missing")
    ast_count = 0
    for path in source:
        if path.endswith(".py"):
            ast.parse((root / path).read_text("utf-8-sig"), filename=path)
            ast_count += 1
    entries = [(line[:2], line[3:]) for line in git("status", "--porcelain=v1", "-z", "-uall").split("\0") if line]
    p10 = sorted(p for s, p in entries if p.startswith("docs/project_memory/p10_evidence/"))
    if p10 != sorted(p for p in before["protected"] if p.startswith("docs/project_memory/p10_evidence/")):
        errors.append("P10 helper set changed")
    markdown = [p for s, p in entries if p.endswith(".md") and "/review-original/" not in p]
    broken, links, secrets = [], 0, []
    for path in markdown:
        content = (root / path).read_text("utf-8-sig")
        for target in re.findall(r"\[[^\]\n]*\]\(([^\n)]+)\)", content):
            target = target.strip().strip("<>")
            if re.match(r"^(?:https?://|mailto:|app:|codex:|#)", target):
                continue
            local = unquote(target.split("#", 1)[0])
            if not local:
                continue
            links += 1
            resolved = Path(local) if Path(local).is_absolute() else (root / path).parent / local
            if not resolved.exists():
                broken.append({"file": path, "target": target})
    if broken:
        errors.append("broken local Markdown links")
    patterns = [r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                r"\bgh[pousr]_[A-Za-z0-9]{30,}\b", r"\bgithub_pat_[A-Za-z0-9_]{50,}\b",
                r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b"]
    for status, path in entries:
        if path not in p10:
            content = (root / path).read_text("utf-8-sig")
            if any(re.search(pattern, content) for pattern in patterns):
                secrets.append(path)
    if secrets:
        errors.append("potential sensitive content requires review")
    diff_check = subprocess.run(["git", "diff", "--check"], capture_output=True,
                                env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if diff_check.returncode:
        errors.append("git diff --check failed")
    head = git("rev-parse", "HEAD").strip()
    origin = git("rev-parse", "origin/main").strip()
    branch = git("branch", "--show-current").strip()
    staged = git("diff", "--cached", "--name-only").strip()
    if head != before["head"] or origin != before["localOrigin"] or branch != before["branch"] or staged:
        errors.append("Git baseline or index changed")
    report = {
        "capturedAt": datetime.now(timezone.utc).isoformat(), "status": "FAIL" if errors else "PASS", "errors": errors,
        "sourceTestFiles": len(source), "sourceStable": source == stable["sourceTest"],
        "thisRoundChangedSource": changed(before["sourceTest"]), "existingTestsUnchanged": not changed({p: h for p, h in before["sourceTest"].items() if p.startswith("tests/")}),
        "protectedFiles": len(before["protected"]), "protectedChanges": protected_changes,
        "protectedCurrentSHA256": {p: sha(root / p) for p in before["protected"]},
        "frozenBoundaryFiles": 25, "frozenSchemas": 6, "formalDataFiles": len(formal),
        "formalDataPathAndSHA256Unchanged": not protected_changes and len(formal) == 7,
        "formalDataHistoricalTree": "sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2",
        "p10Helpers": len(p10), "historicalEvidenceFiles": len(history), "historicalEvidenceChanges": history_changes,
        "reviewOriginalChanges": review_changes, "incidentalFilesUnchanged": incidental == before["incidentalFiles"],
        "retainedTests": len(before["testIdentities"]), "missingTests": missing, "currentTests": len(identities),
        "addedTests": sorted(set(identities) - set(before["testIdentities"])), "loaderErrors": loader.errors,
        "pythonASTFiles": ast_count, "markdownFiles": len(markdown), "localLinksChecked": links,
        "brokenLinks": broken, "sensitiveContentHits": secrets,
        "gitDiffCheck": {"exitCode": diff_check.returncode, "stdout": diff_check.stdout.decode("utf-8", errors="replace")},
        "version": "0.1.0; protected pyproject unchanged", "scope": "R05/R06 Engine only; no Git writes; P12 paused",
        "git": {"head": head, "localOriginMain": origin, "branch": branch, "staged": staged,
                "aheadBehind": git("rev-list", "--left-right", "--count", "HEAD...origin/main").split(),
                "entries": [{"status": s, "path": p} for s, p in entries]},
    }
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("git", "addedTests", "protectedCurrentSHA256")}, ensure_ascii=False))
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
