"""W02 TEST wrapper: data/clock/Fake only, all business wiring in normal C1."""
from dataclasses import replace
from pathlib import Path
from .p08_action_fixture import _validate_fixture_root
from .p09_core_fixture import P09Fixture
from continuity_engine.domain.integration_hashing import calculate_content_hash
from continuity_engine.services.integration_contract_hashing import calculate_request_hash
from continuity_engine.services.continuity_core_service import ContinuityCoreGates


def capture_failure(test, root):
    """Save bounded structural evidence to the runner before TEST root cleanup."""
    import hashlib
    import json
    import sys
    result = test._outcome.result
    if not any(t is test for t, _ in result.failures + result.errors):
        return
    try:
        files = {p.relative_to(root).as_posix(): {'bytes': p.stat().st_size,
                  'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                 for p in sorted(Path(root).rglob('*')) if p.is_file()}
        print(json.dumps({'test': test.id(), 'stage': 'before-TEST-cleanup', 'files': files},
                         ensure_ascii=False), file=sys.stderr)
    except Exception as exc:
        print('W02_DIAGNOSTIC_UNAVAILABLE:' + type(exc).__name__, file=sys.stderr)


class W02InputFixture(P09Fixture):
    def __init__(self, root, *, enabled=True, gates=None, **options):
        _validate_fixture_root(Path(root))
        super().__init__(root, gates=replace(gates or ContinuityCoreGates(), input_processing=enabled), **options)

    def message(self, content='我想吃苹果，但还没有吃。', *, source_event_id=None):
        payload = self.request()
        fact = payload['platformFactPackage']['facts'][0]
        fact['content'] = content
        fact['contentHash'] = calculate_content_hash(content)
        if source_event_id is not None:
            payload['observations'][0]['sourceEventId'] = source_event_id
        payload['requestHash'] = calculate_request_hash(payload)
        return payload

    def record(self, request):
        return self.app.ledger.load_operation(request['requestId']).domain_progress.input_processing


def golden_phase(root, phase):
    import json
    from .sandbox import P01SandboxManager
    from continuity_engine.domain.errors import IntegrationExecutionError
    root = _validate_fixture_root(Path(root))
    manifest = root / 'w02-golden.json'
    if phase == 'prepare':
        f = W02InputFixture(root)
        request = f.message()
        def crash(stage, operation):
            if stage == 'after_c1_action_completed':
                raise RuntimeError('W02_AFTER_TRUSTED_EFFECT')
        f.app.adapter.service._fault_injector = crash
        try:
            f.submit(request)
        except IntegrationExecutionError as exc:
            if str(exc.__cause__) != 'W02_AFTER_TRUSTED_EFFECT':
                raise
        else:
            raise AssertionError('missing controlled interruption')
        saved = {'sandbox': f.runtime.descriptor.sandbox_id, 'request': request,
                 'revision': f.runtime.subject_state().revision,
                 'record': f.record(request).to_dict()}
        manifest.write_text(json.dumps(saved, ensure_ascii=False), encoding='utf-8')
        assert (f.provider.calls, f.adapter.effect_count, f.adapter.credits) == (1, 1, 1)
        return {'phase': phase, 'calls': 1, 'effects': 1, 'credits': 1}
    if phase != 'resume':
        raise ValueError('invalid phase')
    saved = json.loads(manifest.read_text(encoding='utf-8'))
    manager = P01SandboxManager(root/'s', formal_data_roots=(root/'formal-canary',))
    f = W02InputFixture(root, manager=manager, runtime=manager.open_runtime(saved['sandbox']))
    f.submit(saved['request'])
    assert f.record(saved['request']).to_dict() == saved['record']
    assert (f.provider.calls, f.adapter.execute_calls, f.adapter.effect_count, f.adapter.credits) == (0, 0, 1, 1)
    assert f.runtime.subject_state().revision == saved['revision']
    return {'phase': phase, 'calls': 0, 'new_effects': 0, 'total_effects': 1, 'credits': 1,
            'view': f.app.adapter.service.input_outcome(saved['request']['requestId'])}


if __name__ == '__main__':
    import argparse
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--phase', choices=('prepare', 'resume'), required=True)
    args = parser.parse_args()
    print(json.dumps(golden_phase(args.root, args.phase), ensure_ascii=False))
