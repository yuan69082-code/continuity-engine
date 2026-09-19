"""Reuse prior byte-preserved probes, with no test assertion changes."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'docs/project_memory/p18_storage_repair_evidence/independent'))
from test_process_inherited import baseline_suite, advancing_suite
from test_prior_boundary import IndependentPersistenceTests
