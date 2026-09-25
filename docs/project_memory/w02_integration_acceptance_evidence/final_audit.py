"""Read-only W02 acceptance audit; write only this batch's audit summaries."""

import ast
import hashlib
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys
from urllib.parse import unquote


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "src"))
COLLECT = runpy.run_path(str(ROOT / "docs/project_memory/w02_c_evidence/audit.py"))["collect"]
from continuity_engine.testing.persistence import tree_inventory_hash  # noqa: E402

BEFORE = json.loads((ROOT / "docs/project_memory/w02_integration_evidence/baseline.json").read_text(encoding="utf-8"))
DELIVERY = json.loads((ROOT / "docs/project_memory/w02_integration_evidence/final.files.json").read_text(encoding="utf-8"))
FINAL_SOURCE = "sha256:188796ffbc704795291bba912f668f3d415c5173328de307ca9a7e2115d3afd1"
NEW_DOCS = {
    "docs/project_memory/04_决策记录.md",
    "docs/project_memory/05_已完成模块.md",
    "docs/project_memory/w02_integration_acceptance_evidence/acceptance-report.md",
    "docs/project_memory/w02_integration_acceptance_evidence/acceptance-matrix.md",
    "docs/project_memory/w02_integration_acceptance_evidence/audit-preflight-01.md",
    "docs/project_memory/w02_integration_acceptance_evidence/final_audit.py",
}
UPDATED_DOCS = {
    "README.md",
    "docs/project_memory/01_当前状态.md",
    "docs/project_memory/03_施工日志.md",
    "docs/project_memory/06_未完成事项.md",
    "docs/project_memory/10_档案修订记录.md",
    "docs/project_memory/13_P00_档案与测试索引.md",
    "docs/project_memory/CHANGELOG.md",
}
GENERATED = {
    "docs/project_memory/w02_integration_acceptance_evidence/" + filename
    for filename in ("final.audit.json", "final.files.json", "final.pending-files.md")
}
RUNS = ("integration-targeted-01", "w02-abc-compat-01", "public-compat-01", "full-final-01")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.run(("git", *args), cwd=ROOT, capture_output=True, check=False)


def status_paths():
    result = git("-c", "core.quotepath=false", "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if result.returncode:
        raise RuntimeError("GIT_STATUS_FAILED")
    return {item[3:].decode("utf-8"): item[:2].decode("ascii")
            for item in result.stdout.split(bytes([0])) if item}


def missing_links(paths):
    absent = []
    pattern = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
    for name in sorted(paths):
        if not name.endswith(".md") or name in GENERATED:
            continue
        source = ROOT / name
        for target in pattern.findall(source.read_text(encoding="utf-8")):
            local = target.strip().strip("<>").split("#", 1)[0]
            if not local or "://" in local or local.startswith(("mailto:", "#")):
                continue
            resolved = (source.parent / unquote(local)).resolve()
            if not resolved.exists() and resolved not in {(ROOT / item).resolve() for item in GENERATED}:
                absent.append({"source": name, "target": target})
    return absent


def main():
    current = COLLECT()
    rows = status_paths()
    excluded = DELIVERY["excluded"]
    expected_included = set(DELIVERY["included"]) | set(DELIVERY["generated_outputs"]) | NEW_DOCS | GENERATED
    expected_status = expected_included | set(excluded)
    # These three summaries are created only after every pre-write gate passes.
    status_missing = sorted((expected_status - GENERATED) - set(rows))
    status_extra = sorted(set(rows) - expected_status)
    excluded_drift = [name for name, value in excluded.items()
                      if not (ROOT / name).is_file() or sha(ROOT / name) != value]
    earlier_drift = [name for name, value in DELIVERY["included"].items()
                     if name not in UPDATED_DOCS and
                     (not (ROOT / name).is_file() or sha(ROOT / name) != value)]
    source_drift = {name for name in set(BEFORE["source"]) | set(current["source"])
                    if BEFORE["source"].get(name) != current["source"].get(name)}
    wanted_delta = {"src/continuity_engine/services/continuity_core_service.py",
                    "tests/test_w02_integration.py"}
    planning_root = ROOT / "docs/project_memory/w01_planning_v15_20260923/planning"
    planning_ok = all(sha(planning_root / name) == value
                      for name, value in BEFORE["planning"].items())
    ast_errors = []
    for name in sorted(current["source"]):
        if name.endswith(".py"):
            try:
                ast.parse((ROOT / name).read_text(encoding="utf-8"), filename=name)
            except Exception as error:
                ast_errors.append({"path": name, "type": type(error).__name__})
    runs = {}
    run_root = ROOT / "docs/project_memory/w02_integration_evidence"
    for label in RUNS:
        record = json.loads((run_root / (label + ".json")).read_text(encoding="utf-8"))
        stderr = (run_root / (label + ".stderr.log")).read_text(encoding="utf-8")
        count = re.search(r"Ran (\d+) tests? in", stderr)
        runs[label] = {"count": int(count.group(1)) if count else None,
                       "exit_code": record["exit_code"],
                       "elapsed_seconds": record["elapsed_seconds"],
                       "before": record["source_fingerprint_before"],
                       "after": record["source_fingerprint_after"],
                       "stable": record["source_inventory_identical"],
                       "ok": "\nOK" in stderr and "FAILED (" not in stderr}
    remote = git("-c", "http.sslBackend=openssl", "-c", "credential.interactive=never",
                 "ls-remote", "origin", "refs/heads/main")
    remote_sha = remote.stdout.decode("utf-8", "replace").split("\t", 1)[0] if remote.returncode == 0 else None
    diff_check = git("diff", "--check")
    secret_pattern = re.compile(r"(?:sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})")
    secret_hits = [name for name in sorted(expected_included - GENERATED)
                   if name.endswith((".md", ".py")) and
                   secret_pattern.search((ROOT / name).read_text(encoding="utf-8"))]
    links = missing_links(expected_included)
    audit = {
        "branch": current["branch"], "head": current["head"],
        "local_origin": current["localOrigin"], "origin": current["origin"],
        "remote_main_before_git_write": remote_sha,
        "remote_read_exit": remote.returncode,
        "remote_read_error_code": "SEC_E_NO_CREDENTIALS" if b"SEC_E_NO_CREDENTIALS" in remote.stderr else None,
        "staged_paths": sorted(name for name, code in rows.items() if code[0] not in (" ", "?")),
        "status_count": len(rows), "expected_included_count": len(expected_included),
        "excluded_count": len(excluded), "status_missing": status_missing, "status_extra": status_extra,
        "excluded_drift": excluded_drift, "earlier_delivery_drift": earlier_drift,
        "source_count": len(current["source"]), "source_fingerprint": current["sourceHash"],
        "source_delta_is_approved": source_drift == wanted_delta,
        "protected_identical": current["protected"] == BEFORE["protected"],
        "planning_identical": planning_ok,
        "formal_identical": current["formal_files"] == BEFORE["formal_files"],
        "formal_count": len(current["formal_files"]),
        "formal_tree_hash": tree_inventory_hash(ROOT / ".continuity-data"),
        "runs": runs,
        "all_runs_same_source": all(row["exit_code"] == 0 and row["ok"] and row["stable"]
                                and row["before"] == FINAL_SOURCE and row["after"] == FINAL_SOURCE
                                for row in runs.values()),
        "ast_errors": ast_errors, "missing_markdown_links": links,
        "possible_secret_hits": secret_hits,
        "diff_check_exit": diff_check.returncode,
        "diff_check_output": (diff_check.stdout + diff_check.stderr).decode("utf-8", "replace"),
    }
    gates = (audit["branch"] == "main" and audit["head"] == BEFORE["head"]
             and audit["local_origin"] == BEFORE["head"] and remote_sha == BEFORE["head"]
             and not audit["staged_paths"] and not status_missing and not status_extra
             and not excluded_drift and not earlier_drift
             and audit["source_count"] == 297 and current["sourceHash"] == FINAL_SOURCE
             and audit["source_delta_is_approved"] and audit["all_runs_same_source"]
             and audit["protected_identical"] and planning_ok and audit["formal_identical"]
             and audit["formal_count"] == 7
             and audit["formal_tree_hash"] == BEFORE["formal_tree_inventory_hash"]
             and not ast_errors and not links and not secret_hits and diff_check.returncode == 0)
    audit["ready_for_precise_commit"] = bool(gates)
    if not gates:
        print(json.dumps(audit, ensure_ascii=False, indent=2))
        raise RuntimeError("W02_ACCEPTANCE_AUDIT_FAILED")
    files = {
        "source_fingerprint": current["sourceHash"],
        "included": {name: sha(ROOT / name) for name in sorted(expected_included - GENERATED)},
        "generated_outputs": sorted(GENERATED),
        "excluded": {name: sha(ROOT / name) for name in sorted(excluded)},
    }
    (HERE / "final.audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (HERE / "final.files.json").write_text(json.dumps(files, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (HERE / "final.pending-files.md").open("w", encoding="utf-8") as stream:
        stream.write("# W02 整体贯通验收精确提交及排除清单\n\n")
        stream.write(f"应提交 {len(expected_included)} 项；原样排除 {len(excluded)} 项。")
        stream.write("本清单仅记录已获授权的文件；末尾三个自引用审计文件只列路径。\n\n## 应提交\n\n")
        for name in sorted(expected_included):
            stream.write(f"- `{name}`\n")
        stream.write("\n## 排除并保留\n\n")
        for name in sorted(excluded):
            stream.write(f"- `{name}`\n")
    print(json.dumps({"ready_for_precise_commit": bool(gates), "included": len(expected_included),
                      "excluded": len(excluded), "source": current["sourceHash"],
                      "remote_main": remote_sha}, ensure_ascii=False))


if __name__ == "__main__":
    main()
