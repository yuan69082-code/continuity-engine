"""Run one named W02-C verification, preserving first output and identities."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.dont_write_bytecode = True
from audit import collect

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

GROUPS = {
    'formal-final-01': ['tests.test_w02_external_absorption', 'tests.test_w02_external_recovery'],
    'formal-final-02': ['tests.test_w02_external_absorption', 'tests.test_w02_external_recovery'],
    'formal-final-03': ['tests.test_w02_external_absorption', 'tests.test_w02_external_recovery'],
    'formal-final-04': ['tests.test_w02_external_absorption', 'tests.test_w02_external_recovery'],
    'root-boundary-01': [
        'tests.test_w02_external_absorption.ExternalAbsorptionTests.test_external_root_subject_and_environment_binding_fail_closed',
    ],
    'formal-final-05': ['tests.test_w02_external_absorption', 'tests.test_w02_external_recovery'],
    'relevance-fix-01': [
        'tests.test_w02_external_absorption.ExternalAbsorptionTests.test_unrelated_external_material_is_not_selected_for_this_response',
        'tests.test_w02_external_absorption.ExternalAbsorptionTests.test_receipted_root_becomes_pre_answer_candidate_not_subject_fact',
    ],
    'w02-compat-01': [
        'tests.test_w02_input_processing', 'tests.test_w02_input_recovery',
        'tests.test_w02_input_integration', 'tests.test_w02_recall',
        'tests.test_w02_recall_boundaries', 'tests.test_w02_recall_combinations',
        'tests.test_w02_recall_consistency', 'tests.test_w02_recall_semantics',
    ],
    'w02-compat-02': [
        'tests.test_w02_input_processing', 'tests.test_w02_input_recovery',
        'tests.test_w02_input_integration', 'tests.test_w02_recall',
        'tests.test_w02_recall_boundaries', 'tests.test_w02_recall_combinations',
        'tests.test_w02_recall_consistency', 'tests.test_w02_recall_semantics',
    ],
    'w02-compat-03': [
        'tests.test_w02_input_processing', 'tests.test_w02_input_recovery',
        'tests.test_w02_input_integration', 'tests.test_w02_recall',
        'tests.test_w02_recall_boundaries', 'tests.test_w02_recall_combinations',
        'tests.test_w02_recall_consistency', 'tests.test_w02_recall_semantics',
    ],
    'core-compat-01': [
        'tests.test_p04_memory_repository', 'tests.test_p04_memory_consolidation',
        'tests.test_p05_context_router', 'tests.test_p05_context_routing',
        'tests.test_p06_context_composer', 'tests.test_p06_context_composition',
        'tests.test_p16_providers', 'tests.test_p16_context',
        'tests.test_p16_recovery', 'tests.test_p16_review_regressions',
        'tests.test_p16_repair_edges', 'tests.test_p17_execution',
        'tests.test_p17_recovery', 'tests.test_p17_boundaries',
        'tests.test_p17_repair_edges',
    ],
    'core-compat-02': [
        'tests.test_p04_memory_repository', 'tests.test_p04_memory_consolidation',
        'tests.test_p05_context_router', 'tests.test_p05_context_routing',
        'tests.test_p06_context_composer', 'tests.test_p06_context_composition',
        'tests.test_p16_providers', 'tests.test_p16_context',
        'tests.test_p16_recovery', 'tests.test_p16_review_regressions',
        'tests.test_p16_repair_edges', 'tests.test_p17_execution',
        'tests.test_p17_recovery', 'tests.test_p17_boundaries',
        'tests.test_p17_repair_edges',
    ],
    'core-compat-03': [
        'tests.test_p04_memory_repository', 'tests.test_p04_memory_consolidation',
        'tests.test_p05_context_router', 'tests.test_p05_context_routing',
        'tests.test_p06_context_composer', 'tests.test_p06_context_composition',
        'tests.test_p16_providers', 'tests.test_p16_context',
        'tests.test_p16_recovery', 'tests.test_p16_review_regressions',
        'tests.test_p16_repair_edges', 'tests.test_p17_execution',
        'tests.test_p17_recovery', 'tests.test_p17_boundaries',
        'tests.test_p17_repair_edges',
    ],
    'core-compat-04': [
        'tests.test_p04_memory_repository', 'tests.test_p04_memory_consolidation',
        'tests.test_p05_context_router', 'tests.test_p05_context_routing',
        'tests.test_p06_context_composer', 'tests.test_p06_context_composition',
        'tests.test_p16_providers', 'tests.test_p16_context',
        'tests.test_p16_recovery', 'tests.test_p16_review_regressions',
        'tests.test_p16_repair_edges', 'tests.test_p17_execution',
        'tests.test_p17_recovery', 'tests.test_p17_boundaries',
        'tests.test_p17_repair_edges',
    ],
    'full-final-02': ['discover', '-s', 'tests', '-q'],
    'full-final-01': ['discover', '-s', 'tests', '-q'],
}
GROUPS.update({
    'control-boundary-01': [
        'tests.test_w02_external_absorption.ExternalAbsorptionTests.test_external_control_claim_is_not_usable_or_permission',
        'tests.test_w02_external_absorption.ExternalAbsorptionTests.test_ordinary_psychological_material_is_not_screened_as_control_command',
    ],
    'formal-final-06': GROUPS['formal-final-05'],
    'w02-compat-04': GROUPS['w02-compat-03'],
    'core-compat-05': GROUPS['core-compat-04'],
    'full-final-03': GROUPS['full-final-02'],
})


def main():
    label = sys.argv[1]
    if label not in GROUPS:
        raise SystemExit('UNKNOWN_VERIFICATION_LABEL')
    outputs = [HERE / f'{label}.{extension}' for extension in ('json', 'stdout.log', 'stderr.log', 'started.json')]
    if any(path.exists() for path in outputs):
        raise SystemExit('EVIDENCE_LABEL_ALREADY_EXISTS')
    command = [sys.executable, '-m', 'unittest', *GROUPS[label]]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1',
               PYTHONPATH=os.pathsep.join((str(ROOT / 'src'), str(ROOT / 'tests'))))
    start = dt.datetime.now(dt.timezone.utc)
    before = collect()
    with outputs[3].open('x', encoding='utf-8') as stream:
        json.dump({'label': label, 'command': command, 'started_at': start.isoformat(),
                   'source_fingerprint': before['sourceHash']}, stream, indent=2)
        stream.write('\n')
    began = time.monotonic()
    with outputs[1].open('xb') as stdout, outputs[2].open('xb') as stderr:
        proc = subprocess.run(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr, check=False)
    elapsed = time.monotonic() - began
    after = collect()
    result = {
        'label': label, 'command': command, 'cwd': str(ROOT), 'started_at': start.isoformat(),
        'ended_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'elapsed_seconds': elapsed,
        'exit_code': proc.returncode,
        'source_fingerprint_before': before['sourceHash'],
        'source_fingerprint_after': after['sourceHash'],
        'source_inventory_identical': before['source'] == after['source'],
        'formal_identical': before['formal_files'] == after['formal_files'],
        'protected_identical': before['protected'] == after['protected'],
        'excluded_identical': before['excluded'] == after['excluded'],
        'stdout_sha256': hashlib.sha256(outputs[1].read_bytes()).hexdigest(),
        'stderr_sha256': hashlib.sha256(outputs[2].read_bytes()).hexdigest(),
    }
    with outputs[0].open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    print(json.dumps(result, ensure_ascii=False))
    return proc.returncode


if __name__ == '__main__':
    raise SystemExit(main())
