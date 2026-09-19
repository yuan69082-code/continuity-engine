"""Explicit Owner STOP remains terminal for every later control identity."""
from pathlib import Path
import runpy
import tempfile
import unittest

helpers=runpy.run_path(str(Path(__file__).with_name('control_edge_probe.py')))
P18Fixture=helpers['P18Fixture']
from continuity_engine.domain.persistent_runtime import RuntimeBoundaryError

class StopTerminalProbe(unittest.TestCase):
    def test_pause_after_stop_refuses_without_checkpoint_write(self):
        with tempfile.TemporaryDirectory(prefix='p18s-') as directory:
            f=P18Fixture(Path(directory));f.control('STOP','stop-first')
            before=f.store.path.read_bytes()
            with self.assertRaises(RuntimeBoundaryError):f.control('PAUSE','later-pause')
            self.assertEqual(before,f.store.path.read_bytes())
            self.assertEqual(f.host.query()['desired'],'STOPPED')

    def test_second_stop_identity_does_not_corrupt_or_write(self):
        with tempfile.TemporaryDirectory(prefix='p18s-') as directory:
            f=P18Fixture(Path(directory));f.control('STOP','stop-first')
            before=f.store.path.read_bytes();f.control('STOP','stop-second')
            self.assertEqual(before,f.store.path.read_bytes())
            self.assertEqual(f.host.query()['desired'],'STOPPED')

if __name__=='__main__':
    main=helpers['main'];main.__globals__['ControlEdgeProbe']=StopTerminalProbe
    raise SystemExit(main())
