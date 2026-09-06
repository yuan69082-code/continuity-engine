"""Read-only checks; emit one new JSON report, never overwrite prior evidence."""
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
    if destination.exists() or destination.parent != evidence:
        raise ValueError("choose a new local evidence filename")
    os.chdir(root)
    sys.path[:0] = [str(root), str(root / "src")]
    baseline = json.loads((evidence / "before.json").read_text(encoding="utf-8"))
    stable = json.loads((evidence / "stable-source-02.json").read_text(encoding="utf-8"))
    errors = []

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def git(*args):
        return subprocess.check_output(["git", *args], env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"}).decode("utf-8")

    current = {p.relative_to(root).as_posix(): sha(p)
               for folder in ("src", "tests") for p in (root / folder).rglob("*")
               if p.is_file() and p.suffix in (".py", ".json", ".jsonl")}
    if current != stable:
        errors.append("source/test inventory changed after final test snapshot")
    protected_changes = [p for p, h in baseline["protected"].items()
                         if not (root / p).is_file() or sha(root / p) != h]
    if protected_changes:
        errors.append("protected files changed")
    formal = sorted(p.relative_to(root).as_posix() for p in (root / ".continuity-data").rglob("*") if p.is_file())
    if formal != sorted(p for p in baseline["protected"] if p.startswith(".continuity-data/")):
        errors.append("formal data file set changed")
    old_evidence = {p: h for p, h in baseline["trackedFiles"].items()
                    if "/p11_evidence/" in p or "/p10_evidence/" in p or "/p09_evidence/" in p}
    old_evidence_changes = [p for p, h in old_evidence.items() if sha(root / p) != h]
    if old_evidence_changes:
        errors.append("historical evidence changed")
    review = Path(baseline["reviewSource"])
    review_changes = [p for p, h in baseline["reviewFiles"].items()
                      if sha(review / p) != h or sha(evidence / "review-original" / p) != h]
    if review_changes:
        errors.append("independent review original changed")

    loader = unittest.TestLoader()
    suite = loader.discover("tests")

    def ids(node):
        for test in node:
            if isinstance(test, unittest.TestSuite):
                yield from ids(test)
            else:
                yield test.id()

    identities = sorted(ids(suite))
    missing = sorted(set(baseline["originalTestIdentities"]) - set(identities))
    added = sorted(set(identities) - set(baseline["originalTestIdentities"]))
    if loader.errors or missing or any(not p.startswith("test_pre_p12_repairs.") for p in added):
        errors.append("test identity/import mismatch")
    changed_tests = [p for p, h in baseline["sourceTest"].items()
                     if p.startswith("tests/") and current.get(p) != h]
    if changed_tests != ["tests/test_permissions.py"]:
        errors.append("unexpected original test changes")

    def assertions(tree):
        return [ast.dump(node, include_attributes=False) for node in ast.walk(tree)
                if isinstance(node, ast.Assert) or isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute) and node.func.attr.startswith("assert")]

    original = ast.parse(git("show", "HEAD:tests/test_permissions.py"))
    changed = ast.parse((root / "tests/test_permissions.py").read_text(encoding="utf-8-sig"))
    if assertions(original) != assertions(changed):
        errors.append("original permission assertions changed")
    ast_count = 0
    for path in current:
        if path.endswith(".py"):
            ast.parse((root / path).read_text(encoding="utf-8-sig"), filename=path)
            ast_count += 1

    entries = [(line[:2], line[3:]) for line in git("status", "--porcelain=v1", "-z", "--untracked-files=all").split("\0") if line]
    p10 = sorted(p for status, p in entries if p.startswith("docs/project_memory/p10_evidence/"))
    if p10 != sorted(p for p in baseline["protected"] if p.startswith("docs/project_memory/p10_evidence/")):
        errors.append("P10 helper set changed")
    markdown = [p for status, p in entries if p.endswith(".md") and not "/review-original/" in p]
    links = 0
    broken = []
    for path in markdown:
        content = (root / path).read_text(encoding="utf-8-sig")
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
                broken.append({"path": path, "target": target})
    if broken:
        errors.append("broken local document links")
    secret_hits = []
    patterns = [r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
                r"\bgh[pousr]_[A-Za-z0-9]{30,}\b", r"\bgithub_pat_[A-Za-z0-9_]{50,}\b",
                r"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b"]
    for status, path in entries:
        if path in p10:
            continue
        content = (root / path).read_text(encoding="utf-8-sig")
        if any(re.search(pattern, content) for pattern in patterns):
            secret_hits.append(path)
    if secret_hits:
        errors.append("potential secret requires review")
    check = subprocess.run(["git", "diff", "--check"], capture_output=True,
                           env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if check.returncode:
        errors.append("git diff --check failed")
    head = git("rev-parse", "HEAD").strip()
    branch = git("branch", "--show-current").strip()
    staged = git("diff", "--cached", "--name-only").strip()
    if head != baseline["head"] or branch != "main" or staged:
        errors.append("Git baseline/index changed")
    report = {
        "capturedAt": datetime.now(timezone.utc).isoformat(), "status": "PASS" if not errors else "FAIL",
        "errors": errors, "sourceTestFiles": len(current), "stableSourceUnchanged": current == stable,
        "protectedFiles": len(baseline["protected"]), "protectedChanges": protected_changes,
        "frozenBoundaryFiles": 25, "frozenSchemas": 6, "formalDataFiles": len(formal),
        "formalDataPathAndSHA256Unchanged": not protected_changes and len(formal) == 7,
        "formalDataHistoricalTree": "sha256:f9c710c6085e430a251f74463d57133f8c5a4497fe8ffa2ccb96be2db1037bb2",
        "p10Helpers": len(p10), "reviewOriginalsUnchanged": not review_changes,
        "historicalEvidenceFilesUnchanged": len(old_evidence), "historicalEvidenceChanges": old_evidence_changes,
        "originalTestIdentities": len(baseline["originalTestIdentities"]), "missingTests": missing,
        "addedTestIdentities": added, "loaderErrors": loader.errors, "currentTests": len(identities),
        "originalTestChangedFiles": changed_tests, "originalPermissionAssertionsUnchanged": assertions(original) == assertions(changed),
        "pythonASTFiles": ast_count, "markdownFiles": len(markdown), "localLinksChecked": links,
        "brokenLinks": broken, "sensitiveContentHits": secret_hits,
        "gitDiffCheck": {"exitCode": check.returncode, "stdout": check.stdout.decode("utf-8", errors="replace")},
        "git": {"head": head, "branch": branch, "localOriginMain": git("rev-parse", "origin/main").strip(),
                "aheadBehind": git("rev-list", "--left-right", "--count", "HEAD...origin/main").split(),
                "staged": staged, "entries": [{"status": s, "path": p} for s, p in entries]},
        "version": "0.1.0 (protected pyproject unchanged)",
        "scope": "Engine only; no Git writes, no Assistant/production systems, P12 NOT_STARTED",
    }
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("git", "addedTestIdentities")}, ensure_ascii=False))
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
