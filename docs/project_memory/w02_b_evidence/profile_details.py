"""One planned profile, unchanged deadline. Profiling may itself exhaust it."""
import cProfile
import io
from pathlib import Path
import pstats
import tempfile
import unittest
from unittest.mock import patch
from continuity_engine.testing.w02_recall_fixture import W02RecallFixture

class PreparationProfile(unittest.TestCase):
    def test_preparation_cost_locations(self):
        with tempfile.TemporaryDirectory() as root:
            f=W02RecallFixture(Path(root));original=f.core.recall.prepare
            counter=[]
            def measured(*args,**kwargs):
                profile=cProfile.Profile();profile.enable()
                try:return original(*args,**kwargs)
                finally:
                    profile.disable();out=io.StringIO()
                    pstats.Stats(profile,stream=out).strip_dirs().sort_stats('cumtime').print_stats(24)
                    counter.append(1);print('PREPARATION',len(counter));print(out.getvalue())
            with patch.object(f.core.recall,'prepare',side_effect=measured):
                for i,text in enumerate(('我吃了螺蛳粉。','我又在吃螺蛳粉。','我喜欢螺蛳粉。')):
                    f.event('meal'+str(i),content=text)
                    f.submit(f.message(text,source_event_id='meal'+str(i)))
