"""Low-overhead, single planned measurement of the original failing flow."""
from contextlib import ExitStack
import json
import time
from unittest.mock import patch
import tests.test_w02_recall_combinations as original_tests

class CandidateDependencyProfile(original_tests.RecallCombinationTests):
    def test_measure_original_dependency_flow(self):
        original_fixture=original_tests.W02RecallFixture
        def fixture(*args,**kwargs):
            f=original_fixture(*args,**kwargs);prepare=f.core.recall._prepare
            def measured(*args,**kwargs):
                totals={};counts={}
                def timed(name,call):
                    def run(*a,**kw):
                        started=time.perf_counter()
                        try:return call(*a,**kw)
                        finally:
                            totals[name]=totals.get(name,0)+time.perf_counter()-started
                            counts[name]=counts.get(name,0)+1
                    return run
                start=time.perf_counter()
                try:
                    with ExitStack() as stack:
                        for name,obj,method in [('ledger',f.app.ledger,'_load_operations'),
                                ('memory',f.core.memory,'_load_if_exists'),
                                ('timeline',f.core.timeline,'rebuild'),
                                ('candidate',f.core.recall,'_preference_candidates'),
                                ('route',f.core.router,'route'),('compose',f.core.composer,'compose')]:
                            stack.enter_context(patch.object(obj,method,side_effect=timed(name,getattr(obj,method))))
                        return prepare(*args,**kwargs)
                finally:print(json.dumps({'prepare_seconds':time.perf_counter()-start,'nested_seconds':totals,'counts':counts}))
            f.core.recall._prepare=measured
            return f
        with patch.object(original_tests,'W02RecallFixture',side_effect=fixture):
            super().test_new_independent_root_keeps_prior_candidate_source_readable()
