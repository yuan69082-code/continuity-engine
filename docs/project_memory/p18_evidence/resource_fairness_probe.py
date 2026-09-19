"""Bounded self-review of later eligible maintenance behind resource wait."""
from pathlib import Path
import runpy
import tempfile
import unittest

helpers=runpy.run_path(str(Path(__file__).with_name('control_edge_probe.py')))
P18Fixture=helpers['P18Fixture']

class ResourceFairnessProbe(unittest.TestCase):
    def check_later_memory(self,*,tokens=100000,online=True):
        with tempfile.TemporaryDirectory(prefix='p18f-') as directory:
            f=P18Fixture(Path(directory),tokens=tokens);f.online=online
            with f.host.running():
                f.advance(3600);f.host.tick();f.advance(60);f.host.tick()
                self.assertEqual(f.host.query()['activity'],'WAITING_RESOURCES')
                f.base.event('later-local-maintenance')
                before=f.resources.get_resource_state(f.state.subject_id).token_used
                for _ in range(3):f.advance(5);f.host.tick()
                self.assertEqual(f.provider.calls,0)
                self.assertEqual(f.resources.get_resource_state(f.state.subject_id).token_used,before)
                self.assertTrue(f.host.query()['host_alive'])
                memories=f.core.memory.list_memories(f.state.subject_id)
                self.assertTrue(any(m.memory_id=='memory:later-local-maintenance' for m in memories),
                                'eligible later local maintenance must not wait for model resources')

    def test_later_maintenance_with_zero_model_quota(self):
        self.check_later_memory(tokens=0)

    def test_later_maintenance_with_provider_unavailable(self):
        self.check_later_memory(online=False)

if __name__=='__main__':
    main=helpers['main']
    main.__globals__['ControlEdgeProbe']=ResourceFairnessProbe
    raise SystemExit(main())
