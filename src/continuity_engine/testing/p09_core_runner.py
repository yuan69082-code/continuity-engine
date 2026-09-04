"""Reproducible C1 entry using the normal Engine app and isolated P01 roots.

Run: python -m continuity_engine.testing.p09_core_runner --scenario golden
     python -m continuity_engine.testing.p09_core_runner --scenario long
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

from continuity_engine.domain.action_planning import digest
from continuity_engine.domain.integration_results import FirstRoundSuccessResult
from .p09_core_fixture import P09Fixture, P09_FIXTURE_VERSION
from .persistence import atomic_write_json, read_json, tree_inventory_hash
from .sandbox import P01SandboxManager


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def run_golden(root):
    with patch("socket.socket", side_effect=AssertionError("C1 must not open a transport")):
        f = P09Fixture(root)
        observations = []
        for mode in ("direct", "information", "complex", "silence"):
            f.mode = mode
            f.reopen()
            request = f.request()
            result = f.submit(request)
            _require(isinstance(result, FirstRoundSuccessResult), "normal Engine entry failed")
            context = f.context(request)
            action = f.core.last_action
            before = tree_inventory_hash(f.runtime.data_root)
            f.reopen()
            _require(f.submit(request).to_dict() == result.to_dict(), "completed result drift")
            _require(tree_inventory_hash(f.runtime.data_root) == before, "replay wrote data")
            observations.append({"mode": mode, "planner": action.plan is not None,
                "steps": len(action.requests), "trigger": action.requests[0].choice.trigger,
                "context_consumed": context.composition.snapshot.consumable})
        semantic = {"fixture": P09_FIXTURE_VERSION, "rounds": observations,
                    "effects": f.adapter.effect_count, "credits": f.adapter.credits,
                    "revision": f.runtime.subject_state().revision,
                    "formal_access_count": f.manager.formal_access_count}
        return {**semantic, "semantic_hash": digest(semantic)}


def _segment(root, sandbox_id, start, stop):
    start_wall, start_cpu = time.perf_counter(), time.process_time()
    manager = P01SandboxManager(root / "s", formal_data_roots=(root / "formal-canary",))
    runtime = manager.open_runtime(sandbox_id)
    f = P09Fixture(root, runtime=runtime, manager=manager)
    control = root / "runner-checkpoint.json"  # Test driver only; never an Engine source.
    replay_verified = False
    if control.exists():
        previous = read_json(control)
        f.mode = previous["mode"]
        f.reopen()
        before = tree_inventory_hash(f.runtime.data_root)
        result = f.submit(previous["request"])
        _require(digest(result.to_dict()) == previous["result_hash"], "restart result differs")
        _require(tree_inventory_hash(f.runtime.data_root) == before, "restart replay changed data")
        _require(f.provider.calls == 0 and f.adapter.execute_calls == 0, "restart repeated work")
        replay_verified = True
    observations = []
    for i in range(start, stop):
        f.mode = ("direct", "information", "complex")[i % 3]
        f.reopen()
        f.runtime.clock.advance(timedelta(days=1))
        f.event(f"c1-day-{i+1:03d}", content=f"continuity synthetic daily evidence {i+1}")
        request = f.request()
        result = f.submit(request)
        _require(isinstance(result, FirstRoundSuccessResult), "long-run entry failed")
        context = f.context(request)
        _require(context.composition.snapshot.consumable, "missing consumable Context")
        _require(f.runtime.subject_state().revision == 1, "non-authority advanced revision")
        _require(context.route.trace.budget_used <= 50, "Router budget exceeded")
        _require(context.composition.trace.tokens_used <= 768, "Composer budget exceeded")
        expected_effects = sum(x % 3 != 1 for x in range(i + 1))
        _require(f.adapter.effect_count == expected_effects and f.adapter.credits == expected_effects,
                 "effect or credit count drift")
        expected_requests = sum(2 if x % 3 == 2 else 1 for x in range(i + 1))
        ledger = read_json(f.app.ledger.capability_path)
        _require(len(ledger["requests"]) == expected_requests, "duplicate or missing request")
        _require(len(f.app.ledger.list_completed()) == i + 1, "result count drift")
        _require(len(f.core.memory.list_memories(f.runtime.descriptor.subject_id)) == i + 2,
                 "memory consolidation lost an event")
        observations.append({"round": i+1, "logical_time": f.runtime.clock.to_dict()["currentTime"],
            "candidates": context.route.trace.budget_used, "context_tokens": context.composition.trace.tokens_used,
            "fragments": len(context.composition.snapshot.fragments),
            "data_bytes": sum(p.stat().st_size for p in f.runtime.data_root.rglob("*") if p.is_file()),
            "effects": f.adapter.effect_count, "credits": f.adapter.credits})
        atomic_write_json(control, {"mode": f.mode, "request": request, "result_hash": digest(result.to_dict())})
    return {"pid": os.getpid(), "round_start": start, "round_stop": stop,
            "restart_replay_verified": replay_verified, "observations": observations,
            "wall_seconds": round(time.perf_counter()-start_wall, 6),
            "cpu_seconds": round(time.process_time()-start_cpu, 6),
            "formal_access_count": manager.formal_access_count}


def _long_worker_command(root, sandbox_id, start):
    return [sys.executable, "-m", "continuity_engine.testing.p09_core_runner",
            "--worker-root", str(root), "--sandbox-id", sandbox_id,
            "--start", str(start), "--stop", str(start + 10)]


def _redact_test_evidence(value):
    """Keep local TEST diagnostics, without copying fixture data or credentials."""
    value = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----",
                   "[REDACTED PRIVATE KEY]", value)
    value = re.sub(r"(?i)(authorization\s*:\s*bearer\s+)\S+", r"\1[REDACTED]", value)
    value = re.sub(r"(?i)(\b(?:api[_-]?key|access[_-]?token|password|secret)\b[\"']?\s*[:=]\s*[\"']?)[^\s\"',;]+",
                   r"\1[REDACTED]", value)
    return re.sub(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}", "[REDACTED KEY]", value)


def _preserve_long_failure(root, started_at, started_clock, phase, records, error):
    # A fresh, independent directory survives TemporaryDirectory cleanup. This
    # is a TEST evidence artifact, never an Engine store or a recovery ledger.
    destination = Path(tempfile.mkdtemp(prefix="c1e-"))
    if destination.resolve().is_relative_to(Path(root).resolve()):
        raise ValueError("failure evidence must be outside the disposable fixture")
    saved = []
    for record in records:
        item = dict(record)
        item["command"] = [_redact_test_evidence(str(arg)) for arg in record["command"]]
        for stream in ("stdout", "stderr"):
            name = f"{record['stage']}.{stream}.log"
            source = Path(root) / name
            raw = source.read_bytes() if source.exists() else b""
            text = raw.decode("utf-8", errors="replace")
            sanitized = _redact_test_evidence(text)
            with (destination / name).open("xb") as output:
                output.write(sanitized.encode("utf-8") if sanitized != text else raw)
            item[stream] = {"file": name, "source_present": source.exists(),
                            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                            "redacted": sanitized != text}
        saved.append(item)
    metadata = {"format": "p09-long-failure-v1", "fixture": P09_FIXTURE_VERSION,
                "fixture_root": str(Path(root).resolve()), "phase": phase,
                "started_at_utc": started_at,
                "failed_at_utc": datetime.now(timezone.utc).isoformat(),
                "wall_seconds": round(time.perf_counter() - started_clock, 6),
                "exception_type": type(error).__name__,
                "exception_message": _redact_test_evidence(str(error)),
                "parent_interrupted": isinstance(error, KeyboardInterrupt),
                "retry_count": 0, "segments": saved}
    with (destination / "metadata.json").open("x", encoding="utf-8") as output:
        json.dump(metadata, output, ensure_ascii=False, indent=2)
        output.write("\n")
    return destination


def run_long(root, *, rounds=30):
    if rounds != 30:
        raise ValueError("the versioned C1 long scenario is fixed at 30 logical days/rounds")
    started_at = datetime.now(timezone.utc).isoformat()
    started_clock = time.perf_counter()
    records, segments = [], []
    phase = "fixture"
    try:
        f = P09Fixture(root)
        for start in (0, 10, 20):
            phase = f"segment-{start}"
            command = _long_worker_command(root, f.runtime.descriptor.sandbox_id, start)
            record = {"stage": phase, "command": command,
                      "started_at_utc": datetime.now(timezone.utc).isoformat(),
                      "exit_code": None, "parent_interrupted": False,
                      "child_interrupt_exit": False}
            records.append(record)
            stdout, stderr = root / f"{phase}.stdout.log", root / f"{phase}.stderr.log"
            try:
                # Stream into files so a parent interrupt cannot discard a
                # child's already-written output held in communicate() buffers.
                with stdout.open("xb") as out, stderr.open("xb") as err:
                    with subprocess.Popen(command, stdout=out, stderr=err,
                            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}) as child:
                        try:
                            record["exit_code"] = child.wait()
                        except BaseException:
                            if child.poll() is None:
                                child.terminate()
                                try:
                                    child.wait(timeout=5)
                                except subprocess.TimeoutExpired:
                                    child.kill()
                                    child.wait()
                            record["exit_code"] = child.returncode
                            raise
            except KeyboardInterrupt:
                record["parent_interrupted"] = True
                raise
            finally:
                record["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
                record["child_interrupt_exit"] = record["exit_code"] in (-2, 130, -1073741510, 3221225786)
            if record["exit_code"]:
                raise RuntimeError(f"C1 segment {start} failed with exit code {record['exit_code']}")
            segments.append(json.loads(stdout.read_text(encoding="utf-8")))
        phase = "validate-long-report"
        _require(len({s["pid"] for s in segments}) == 3, "workers did not restart")
        _require(all(s["restart_replay_verified"] for s in segments[1:]), "restart not verified")
        return {"fixture": P09_FIXTURE_VERSION, "logical_days": 30, "rounds": 30,
                "new_events": 30, "restart_after_rounds": [10, 20], "segments": segments,
                "no_full_chat_history": True, "production_soak_claim": False}
    except BaseException as error:
        try:
            error.evidence_path = _preserve_long_failure(root, started_at, started_clock, phase, records, error)
            error.add_note(f"P09_TEST_FAILURE_EVIDENCE: {error.evidence_path}")
        except Exception as preservation_error:
            error.add_note(f"P09_TEST_EVIDENCE_SAVE_FAILED: {type(preservation_error).__name__}")
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description="C1 normal Engine entry in a disposable P01 sandbox")
    parser.add_argument("--scenario", choices=("golden", "long"), default="golden")
    parser.add_argument("--worker-root", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--sandbox-id", help=argparse.SUPPRESS)
    parser.add_argument("--start", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--stop", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    if args.worker_root:
        with patch("socket.socket", side_effect=AssertionError("C1 transport forbidden")):
            report = _segment(args.worker_root, args.sandbox_id, args.start, args.stop)
    else:
        root = Path(tempfile.mkdtemp(prefix="c1"))
        report = run_golden(root) if args.scenario == "golden" else run_long(root)
        report["isolated_evidence_root"] = str(root)
        atomic_write_json(root / "c1-report.json", report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
