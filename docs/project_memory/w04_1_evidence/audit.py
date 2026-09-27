"""Read-only W04-1 delivery inventory; writes evidence only, never Git."""
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
PRIOR = json.loads((ROOT / "docs/project_memory/planning_v16_20260927/final.audit.repair-01.json").read_text(encoding="utf-8"))
BASE = json.loads((ROOT / "docs/project_memory/w02_a_evidence/baseline.json").read_text(encoding="utf-8"))
EXCLUDED = json.loads((ROOT / "docs/project_memory/w02_a_acceptance_evidence/exclusions.json").read_text(encoding="utf-8"))["all57"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", "-c", "core.quotepath=false", *args], cwd=ROOT).decode("utf-8").strip()


def w04_paths():
    specific = {
        "docs/project_memory/01_当前状态.md", "docs/project_memory/03_施工日志.md",
        "docs/project_memory/04_决策记录.md", "docs/project_memory/06_未完成事项.md",
        "docs/project_memory/10_档案修订记录.md", "docs/project_memory/工程总档案.md",
        "src/continuity_engine/domain/environment_access.py",
        "src/continuity_engine/storage/json_environment_repository.py",
        "src/continuity_engine/services/environment_access_service.py",
        "src/continuity_engine/services/scoped_history_service.py",
        "src/continuity_engine/services/continuity_interaction_service.py",
        "src/continuity_engine/services/execution_service.py",
        "tests/test_w04_1_environment.py",
    }
    return sorted(specific | {p.relative_to(ROOT).as_posix() for p in HERE.iterdir() if p.is_file()})


def main():
    pending = HERE / "final.pending-files-03.md"
    audit = HERE / "final.audit-03.json"
    if pending.exists() or audit.exists():
        raise SystemExit("final inventory already exists; never overwrite")
    paths = w04_paths() + ["docs/project_memory/w04_1_evidence/final.pending-files-03.md",
                           "docs/project_memory/w04_1_evidence/final.audit-03.json"]
    paths = sorted(set(paths))
    pending.write_text("# W04-1 精确交付清单（未暂存）\n\n"
                       "本批 `IMPLEMENTED_NOT_ACCEPTED`，不包含 D-085 的既有 20 项规划归档；"
                       "与之重叠的六份当前档案列在下表，并在终局审计中单独标记。"
                       "原 57 项保留材料不列入本批；其中规划索引是前置授权变动。\n\n"
                       "| 相对路径 | SHA-256 |\n|---|---|\n" + "\n".join(
                           f"| `{p}` | `{sha(ROOT / p)}` |" for p in paths
                           if p not in {"docs/project_memory/w04_1_evidence/final.pending-files-03.md",
                                        "docs/project_memory/w04_1_evidence/final.audit-03.json"})
                       + "\n\n以上两份自引用档案也在本批清单内，其 SHA-256 由独立读取计算；"
                       "`final.audit-03.json` 记录本清单 hash，审计文件不对自身声称固定 hash。\n",
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
            if target and not target.startswith(("http:", "https:")) and (file.parent / target) != audit and not (file.parent / target).exists():
                missing_links.append(f"{file.name}: {target}")
    protected = BASE["protected"]["protected"]
    formal = BASE["protected"]["formalFiles"]
    planning = json.loads((ROOT / "docs/project_memory/planning_v16_20260927/planning-sources.json").read_text(encoding="utf-8"))["sources"]
    status = set(filter(None, git("ls-files", "-m", "-o", "--exclude-standard").splitlines()))
    prior_paths = set(PRIOR["deliveryPaths"])
    excluded_paths = set(EXCLUDED)
    expected_status = set(paths) - {"docs/project_memory/w04_1_evidence/final.audit-03.json"} | prior_paths | excluded_paths
    mismatched_protected = [p for p, old in protected.items() if sha(ROOT / p) != old]
    mismatched_formal = [p for p, old in formal.items() if sha(ROOT / p) != old]
    mismatched_plans = [row["archivePath"] for row in planning
                        if sha(ROOT / row["archivePath"]) != row["archiveSha256"]]
    changed_excluded = [p for p, old in EXCLUDED.items() if sha(ROOT / p) != old]
    prior_hash_checks = {}
    for path in prior_paths - set(paths):
        expected = PRIOR["deliverySha256ExcludingSelf"].get(path)
        if path == "docs/project_memory/planning_v16_20260927/final.audit.json":
            expected = PRIOR["priorAuditSha256"]
        prior_hash_checks[path] = (sha(ROOT / path) == expected if expected else "NO_PRIOR_SELF_HASH")
    data = {
        "kind": "w04_1_final_audit", "at_utc": datetime.now(timezone.utc).isoformat(),
        "branch": git("branch", "--show-current"), "head": git("rev-parse", "HEAD"),
        "local_origin_main": git("rev-parse", "origin/main"),
        "staged": git("diff", "--cached", "--name-only"),
        "source_count": len(source), "source_fingerprint": SNAPSHOT["fingerprint"](source),
        "syntax_errors": syntax_errors, "missing_w04_markdown_links": missing_links,
        "protected_count": len(protected), "protected_mismatch": mismatched_protected,
        "formal_count": len(formal), "formal_mismatch": mismatched_formal,
        "planning_mismatch": mismatched_plans,
        "prior_planning_delivery_count": len(prior_paths),
        "prior_planning_hash_checks": dict(sorted(prior_hash_checks.items())),
        "old_exclusion_count": len(EXCLUDED), "old_exclusion_changed": changed_excluded,
        "authorized_planning_index_changed": changed_excluded == ["docs/project_memory/现行规划版本索引.md"],
        "w04_delivery_count": len(paths), "w04_delivery_paths": paths,
        "w04_hashes_excluding_audit": {p: sha(ROOT / p) for p in paths if p != "docs/project_memory/w04_1_evidence/final.audit-03.json"},
        "unexpected_status_paths": sorted(status - expected_status),
        "missing_w04_status_paths": sorted(set(paths) - status - {"docs/project_memory/w04_1_evidence/final.audit-03.json"}),
        "git_writes": False,
    }
    audit.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: data[k] for k in ("source_count", "source_fingerprint", "syntax_errors",
               "missing_w04_markdown_links", "protected_mismatch",
               "formal_mismatch", "planning_mismatch", "old_exclusion_changed", "unexpected_status_paths",
               "missing_w04_status_paths", "w04_delivery_count")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
