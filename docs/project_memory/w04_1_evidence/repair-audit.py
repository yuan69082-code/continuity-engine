"""Create a new W04-1 repair inventory without overwriting prior evidence."""
from __future__ import annotations

import ast
import hashlib
import json
import re
import runpy
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
SNAPSHOT = runpy.run_path(str(ROOT / "docs/project_memory/w02_b_evidence/snapshot.py"))
OLD = json.loads((HERE / "final.audit-03.json").read_text(encoding="utf-8"))
PRIOR = json.loads((ROOT / "docs/project_memory/planning_v16_20260927/final.audit.repair-01.json").read_text(encoding="utf-8"))
BASE = json.loads((ROOT / "docs/project_memory/w02_a_evidence/baseline.json").read_text(encoding="utf-8"))
EXCLUDED = json.loads((ROOT / "docs/project_memory/w02_a_acceptance_evidence/exclusions.json").read_text(encoding="utf-8"))["all57"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", "-c", "core.quotepath=false", *args], cwd=ROOT).decode("utf-8").strip()


def main():
    pending = HERE / "repair-final.pending-files.md"
    audit = HERE / "repair-final.audit.json"
    if pending.exists() or audit.exists():
        raise SystemExit("repair inventory label already exists; never overwrite")
    existing = set(OLD["w04_delivery_paths"])
    additions = {p.relative_to(ROOT).as_posix() for p in HERE.iterdir()
                 if p.is_file() and p.name.startswith(("w04-r1-", "repair-"))}
    paths = sorted(existing | additions | {pending.relative_to(ROOT).as_posix(), audit.relative_to(ROOT).as_posix()})
    rows = [f"| `{path}` | `{sha(ROOT / path)}` |" for path in paths
            if path not in {pending.relative_to(ROOT).as_posix(), audit.relative_to(ROOT).as_posix()}]
    pending.write_text(
        "# W04-1 返修后精确交付清单（未暂存）\n\n"
        "累计 W04-1 成果包含原 66 项与本轮新增证据；D-085 前置规划 20 项单列。"
        "原 57 项保留材料不在本清单；现行规划索引是 D-085 的授权变更。"
        "本清单和审计自身不声称固定自己的 hash，审计记录本清单 hash。\n\n"
        "| 相对路径 | SHA-256 |\n|---|---|\n" + "\n".join(rows) + "\n",
        encoding="utf-8")

    source = SNAPSHOT["source"]()
    syntax_errors = []
    for path in source:
        if path.endswith(".py"):
            try:
                ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)
            except (SyntaxError, UnicodeError) as exc:
                syntax_errors.append(f"{path}: {type(exc).__name__}")
    missing_links = []
    for file in HERE.glob("*.md"):
        for target in re.findall(r"\]\(([^)]+)\)", file.read_text(encoding="utf-8")):
            target = unquote(target.split("#", 1)[0])
            resolved = file.parent / target
            if (target and not target.startswith(("http:", "https:"))
                    and resolved not in (pending, audit) and not resolved.exists()):
                missing_links.append(f"{file.name}: {target}")

    protected = BASE["protected"]["protected"]
    formal = BASE["protected"]["formalFiles"]
    planning = json.loads((ROOT / "docs/project_memory/planning_v16_20260927/planning-sources.json").read_text(encoding="utf-8"))["sources"]
    status = set(filter(None, git("ls-files", "-m", "-o", "--exclude-standard").splitlines()))
    expected_status = set(paths) | set(PRIOR["deliveryPaths"]) | set(EXCLUDED)
    old_hashes = OLD["w04_hashes_excluding_audit"]
    prior_hashes = PRIOR["deliverySha256ExcludingSelf"]
    prior_only = set(PRIOR["deliveryPaths"]) - set(paths)
    data = {
        "kind": "w04_1_repair_final_audit", "at_utc": datetime.now(timezone.utc).isoformat(),
        "branch": git("branch", "--show-current"), "head": git("rev-parse", "HEAD"),
        "local_origin_main": git("rev-parse", "origin/main"),
        "staged": git("diff", "--cached", "--name-only"),
        "source_count": len(source), "source_fingerprint": SNAPSHOT["fingerprint"](source),
        "source_changed_from_prior_w04": sorted(path for path, old in old_hashes.items()
            if path.startswith(("src/", "tests/")) and sha(ROOT / path) != old),
        "syntax_errors": syntax_errors, "missing_w04_markdown_links": missing_links,
        "protected_count": len(protected),
        "protected_mismatch": [path for path, old in protected.items() if sha(ROOT / path) != old],
        "formal_count": len(formal),
        "formal_mismatch": [path for path, old in formal.items() if sha(ROOT / path) != old],
        "planning_mismatch": [row["archivePath"] for row in planning
                              if sha(ROOT / row["archivePath"]) != row["archiveSha256"]],
        "prior_planning_delivery_count": len(PRIOR["deliveryPaths"]),
        "prior_planning_hash_checks": {path: (sha(ROOT / path) == prior_hashes[path])
                                      if path in prior_hashes else "NO_PRIOR_SELF_HASH"
                                      for path in sorted(prior_only)},
        "old_exclusion_count": len(EXCLUDED),
        "old_exclusion_changed": [path for path, old in EXCLUDED.items() if sha(ROOT / path) != old],
        "w04_prior_delivery_count": len(existing), "w04_repair_added_count": len(set(paths) - existing),
        "w04_delivery_count": len(paths), "w04_delivery_paths": paths,
        "w04_hashes_excluding_audit_and_manifest": {path: sha(ROOT / path) for path in paths
                                                    if path not in {pending.relative_to(ROOT).as_posix(),
                                                                    audit.relative_to(ROOT).as_posix()}},
        "pending_manifest_sha256": sha(pending),
        "unexpected_status_paths": sorted(status - expected_status),
        "missing_w04_status_paths": sorted(set(paths) - status - {audit.relative_to(ROOT).as_posix()}),
        "git_writes": False,
    }
    audit.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: data[key] for key in (
        "source_count", "source_fingerprint", "source_changed_from_prior_w04", "syntax_errors",
        "missing_w04_markdown_links", "protected_mismatch", "formal_mismatch",
        "planning_mismatch", "old_exclusion_changed", "unexpected_status_paths",
        "missing_w04_status_paths", "w04_delivery_count")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
