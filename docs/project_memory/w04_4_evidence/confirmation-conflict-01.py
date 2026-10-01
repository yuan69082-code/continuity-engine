"""One bounded real-entry diagnostic, before native delivery; no policy changes."""
import json
import tempfile
from pathlib import Path
from continuity_engine.testing.w04_cross_entry_fixture import W04EntryFixture

with tempfile.TemporaryDirectory(prefix='w04-4-confirmation-') as root:
    f = W04EntryFixture(Path(root))
    original = f.core.expression_policy.decide
    recorded = []
    def inspect(core, operation, thinking, action, context):
        request = core.expression_policy.authorization_request(core, operation, context, thinking, action)
        artifact = original(core, operation, thinking, action, context)
        recorded.append(dict(operation=operation.operation_id, request=operation.request_id,
            action_approved=action.decision.approved, action_requires_confirmation=action.decision.requires_confirmation,
            exact_expression_confirmation=core.constraints.confirmed(request), expression_status=artifact.status,
            expression_reasons=artifact.reason_codes))
        return artifact
    f.core.expression_policy.decide = inspect
    try:
        f.submit('周六选河边店还是山坡店？')
        outcome = 'UNEXPECTED_SUCCESS'
    except Exception as exc:
        outcome = type(exc).__name__
    # Save structural TEST diagnostics before root cleanup; no arbitrary repr.
    print(json.dumps(dict(outcome=outcome, observations=recorded,
        model_calls=len(f.provider.inputs), effects={k:p.effect_count for k,p in f.ports.items()},
        credits={k:p.credits for k,p in f.ports.items()}), ensure_ascii=False))
