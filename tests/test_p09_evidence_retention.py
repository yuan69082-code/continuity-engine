"""P09 long-run failures must outlive the disposable fixture scope."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from continuity_engine.testing import p09_core_runner as runner


class P09EvidenceRetentionTests(unittest.TestCase):
    def failure_command(self, code=91, stdout="synthetic-child-output", stderr="synthetic-child-failure"):
        return [sys.executable, "-c", "import sys; "
                f"print({stdout!r}, flush=True); print({stderr!r}, file=sys.stderr, flush=True); sys.exit({code})"]

    def retained(self, error):
        path = getattr(error, "evidence_path", None)
        self.assertIsNotNone(path, "child failure has no evidence outside the cleaned fixture")
        path = Path(path)
        self.assertTrue(path.is_dir())
        self.assertIn(str(path), " ".join(error.__notes__))
        return path, json.loads((path / "metadata.json").read_text(encoding="utf-8"))

    def test_child_failure_evidence_survives_fixture_cleanup(self):
        command = self.failure_command()
        with tempfile.TemporaryDirectory(prefix="p9e-") as directory:
            root = Path(directory)
            with patch.object(runner, "_long_worker_command", return_value=command) as launch:
                with self.assertRaises(RuntimeError) as caught:
                    runner.run_long(root)
                self.assertEqual(launch.call_count, 1)
        self.assertFalse(root.exists())
        retained, metadata = self.retained(caught.exception)
        self.assertFalse(retained.is_relative_to(root))
        self.assertIn("synthetic-child-failure", (retained / "segment-0.stderr.log").read_text(encoding="utf-8"))
        self.assertIn("synthetic-child-output", (retained / "segment-0.stdout.log").read_text(encoding="utf-8"))
        record = metadata["segments"][0]
        for stream in ("stdout", "stderr"):
            saved = (retained / record[stream]["file"]).read_bytes()
            self.assertFalse(record[stream]["redacted"])
            self.assertEqual(len(saved), record[stream]["bytes"])
            self.assertEqual(hashlib.sha256(saved).hexdigest(), record[stream]["sha256"])
        self.assertEqual(record["command"], command)
        self.assertEqual(record["exit_code"], 91)
        self.assertEqual(metadata["phase"], "segment-0")
        self.assertFalse(metadata["parent_interrupted"])
        self.assertEqual(metadata["retry_count"], 0)
        self.assertLessEqual(record["started_at_utc"], record["finished_at_utc"])
        self.assertLessEqual(metadata["started_at_utc"], metadata["failed_at_utc"])
        print("RETAINED_CONTROLLED_FAILURE", retained, "exit_code=91", flush=True)

    def test_later_failure_retains_prior_segment_and_never_starts_next(self):
        valid = json.dumps({"pid": 101, "restart_replay_verified": False})
        with tempfile.TemporaryDirectory(prefix="p9e-") as directory:
            with patch.object(runner, "_long_worker_command", side_effect=[
                    self.failure_command(0, valid, ""), self.failure_command()]) as launch:
                with self.assertRaises(RuntimeError) as caught:
                    runner.run_long(Path(directory))
                self.assertEqual(launch.call_count, 2)
        retained, metadata = self.retained(caught.exception)
        self.assertEqual(metadata["phase"], "segment-10")
        self.assertEqual([r["exit_code"] for r in metadata["segments"]], [0, 91])
        self.assertEqual(json.loads((retained / "segment-0.stdout.log").read_text()), json.loads(valid))
        self.assertIn("synthetic-child-failure", (retained / "segment-10.stderr.log").read_text())
        self.assertFalse((retained / "segment-20.stderr.log").exists())

    def test_parent_interrupt_preserves_partial_streams_and_actual_exit_code(self):
        real_popen = subprocess.Popen
        children = []
        with tempfile.TemporaryDirectory(prefix="p9e-") as directory:
            root = Path(directory)
            ready = root / "controlled-ready"
            command = [sys.executable, "-c", "import sys,time; from pathlib import Path; "
                       "print('partial-stdout',flush=True); print('partial-stderr',file=sys.stderr,flush=True); "
                       f"Path({str(ready)!r}).write_text('ready'); time.sleep(30)"]
            def launch(*args, **kwargs):
                child = real_popen(*args, **kwargs)
                children.append(child)
                original_wait = child.wait
                interrupted = False
                def wait(*a, **kw):
                    nonlocal interrupted
                    if not interrupted:
                        interrupted = True
                        deadline = time.monotonic() + 5
                        while not ready.exists():
                            if time.monotonic() >= deadline:
                                raise AssertionError("controlled child did not write its streams")
                            time.sleep(0.01)
                        raise KeyboardInterrupt("controlled parent interrupt")
                    return original_wait(*a, **kw)
                child.wait = wait
                return child
            with patch.object(runner, "_long_worker_command", return_value=command), \
                    patch.object(runner.subprocess, "Popen", side_effect=launch):
                with self.assertRaises(KeyboardInterrupt) as caught:
                    runner.run_long(root)
        self.assertFalse(root.exists())
        retained, metadata = self.retained(caught.exception)
        self.assertTrue(metadata["parent_interrupted"])
        self.assertTrue(metadata["segments"][0]["parent_interrupted"])
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].returncode)
        self.assertEqual(metadata["segments"][0]["exit_code"], children[0].returncode)
        self.assertIn("partial-stdout", (retained / "segment-0.stdout.log").read_text())
        self.assertIn("partial-stderr", (retained / "segment-0.stderr.log").read_text())
        print("RETAINED_CONTROLLED_INTERRUPT", retained, "exit_code=", children[0].returncode, flush=True)

    def test_distinct_failures_do_not_overwrite_first_evidence(self):
        paths = []
        with tempfile.TemporaryDirectory(prefix="p9e-") as directory:
            root = Path(directory)
            canary = root / "unrelated.txt"
            canary.write_text("unrelated test material", encoding="utf-8")
            for code in (91, 130):
                with patch.object(runner, "_long_worker_command", return_value=self.failure_command(code)):
                    with self.assertRaises(RuntimeError) as caught:
                        runner.run_long(root / str(code))
                retained, metadata = self.retained(caught.exception)
                paths.append(retained)
                self.assertEqual(metadata["segments"][0]["exit_code"], code)
                self.assertEqual(metadata["segments"][0]["child_interrupt_exit"], code == 130)
                self.assertFalse(metadata["parent_interrupted"])
                if code == 91:
                    first_bytes = (retained / "metadata.json").read_bytes()
            self.assertEqual(canary.read_text(), "unrelated test material")
        self.assertNotEqual(*paths)
        self.assertEqual((paths[0] / "metadata.json").read_bytes(), first_bytes)

    def test_saved_diagnostics_redact_secrets_without_copying_fixture_state(self):
        secret = "synthetic-sensitive-value"
        command = self.failure_command(91, "api_key=" + secret, "Authorization: Bearer " + secret)
        with tempfile.TemporaryDirectory(prefix="p9e-") as directory:
            with patch.object(runner, "_long_worker_command", return_value=command):
                with self.assertRaises(RuntimeError) as caught:
                    runner.run_long(Path(directory))
        retained, metadata = self.retained(caught.exception)
        self.assertEqual({p.name for p in retained.iterdir()},
                         {"metadata.json", "segment-0.stdout.log", "segment-0.stderr.log"})
        for path in retained.iterdir():
            self.assertNotIn(secret, path.read_text(encoding="utf-8"))
        self.assertTrue(metadata["segments"][0]["stdout"]["redacted"])
        self.assertTrue(metadata["segments"][0]["stderr"]["redacted"])
        self.assertEqual(len(metadata["segments"][0]["stderr"]["sha256"]), 64)

    def test_invalid_success_output_is_retained_as_parent_validation_failure(self):
        with tempfile.TemporaryDirectory(prefix="p9e-") as directory:
            with patch.object(runner, "_long_worker_command", return_value=self.failure_command(0, "invalid-json")):
                with self.assertRaises(json.JSONDecodeError) as caught:
                    runner.run_long(Path(directory))
        retained, metadata = self.retained(caught.exception)
        self.assertEqual(metadata["segments"][0]["exit_code"], 0)
        self.assertEqual(metadata["exception_type"], "JSONDecodeError")
        self.assertIn("invalid-json", (retained / "segment-0.stdout.log").read_text())


if __name__ == "__main__":
    unittest.main()
