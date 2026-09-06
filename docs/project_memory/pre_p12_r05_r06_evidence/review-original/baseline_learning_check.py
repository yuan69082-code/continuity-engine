"""Read HEAD's LearningService into memory; never check out or edit Engine."""
import subprocess
import types
import unittest
from unittest.mock import patch

import recheck_probes

repo = r"C:\Users\Administrator\Documents\continuity-engine"
git = r"C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe"
source = subprocess.check_output([
    git, "-c", "safe.directory=" + repo, "-C", repo,
    "show", "5f25d0cef3798aa380d457ae670db30ee1b47407:src/continuity_engine/services/learning_service.py",
]).decode("utf-8")
module = types.ModuleType("continuity_engine.services._review_pre_repair_learning")
module.__package__ = "continuity_engine.services"
exec(compile(source, "HEAD:learning_service.py", "exec"), module.__dict__)
case = recheck_probes.RecheckProbes(
    "test_extra_freshly_validated_learning_with_unchanged_support_can_solidify"
)
with patch.object(recheck_probes.original, "LearningService", module.LearningService):
    result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([case]))
raise SystemExit(0 if result.wasSuccessful() else 1)
