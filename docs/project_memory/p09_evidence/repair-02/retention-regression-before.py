"""P09 long-run failures must outlive the disposable fixture scope."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.testing import p09_core_runner as runner


class P09EvidenceRetentionTests(unittest.TestCase):
    def test_child_failure_evidence_survives_fixture_cleanup(self):
        with tempfile.TemporaryDirectory(prefix="p9e-") as directory:
            root = Path(directory)
            with patch.object(runner.subprocess, "run", return_value=subprocess.CompletedProcess(
                    ["controlled-test-child"], 91, b"synthetic-child-output\n", b"synthetic-child-failure\n")):
                with self.assertRaises(RuntimeError) as caught:
                    runner.run_long(root)
            retained = getattr(caught.exception, "evidence_path", None)
        self.assertFalse(root.exists())
        self.assertIsNotNone(retained, "child failure has no evidence outside the cleaned fixture")
        self.assertTrue(Path(retained).is_dir())
        self.assertIn("synthetic-child-failure", (Path(retained) / "segment-0.stderr.log").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
