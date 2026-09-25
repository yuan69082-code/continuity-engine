"""One-shot isolated child for a real W02-C process reopen regression."""
import json
import sys
from pathlib import Path

from continuity_engine.testing.sandbox import P01SandboxManager
from continuity_engine.testing.w02_c_fixture import W02CFixture


def main():
    root=Path(sys.argv[1])
    sandbox_id=sys.argv[2]
    manager=P01SandboxManager(root/'s',formal_data_roots=(root/'formal-canary',))
    runtime=manager.open_runtime(sandbox_id)
    fixture=W02CFixture(root,runtime=runtime,manager=manager)
    if sys.argv[3] == 'verify-withdrawal':
        memory=fixture.core.memory.load_memory(fixture.state.subject_id,sys.argv[4])
        summary=fixture.core.memory.load_summary(fixture.state.subject_id,sys.argv[5])
        print(json.dumps({'memory_current':fixture.absorption.memory_current(memory),
                          'summary_current':fixture.absorption.summary_current(summary,fixture.core.memory),
                          'revision':fixture.state.revision,
                          'facts':len(fixture.base.fake.facts())}))
        return
    request=json.loads(Path(sys.argv[3]).read_text(encoding='utf-8'))
    fixture.submit(request)
    print(json.dumps({'external_calls':fixture.external_calls,
                      'revision':fixture.state.revision,
                      'cache_entries':len(fixture.base.registry.cached()),
                      'absorbed_entries':len(fixture.base.external.absorbed())}))


if __name__=='__main__':main()
