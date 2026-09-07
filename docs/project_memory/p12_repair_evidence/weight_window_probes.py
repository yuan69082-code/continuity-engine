"""R5: bounded windows must seal their current consumption weight, Temp only."""
from pathlib import Path
import tempfile
import unittest
from continuity_engine.domain.memory import MemoryRecord
from continuity_engine.testing.p12_memory_fixture import P12MemoryFixture
from continuity_engine.services.context_router_service import MemoryContextSource, DerivedSummaryContextSource, ContextSourceQuery


class WeightWindowProbes(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='p12-weight-window-'); self.addCleanup(temporary.cleanup)
        self.f=P12MemoryFixture(Path(temporary.name)/'f'); self.parent=self.f.golden.memories[0]
        body=self.parent.to_dict()
        body.update(memory_id='weight-alias',consolidation_id='weight-alias-op',consolidation_input_hash=None,
                    scope='review:window',content='review derived evidence',tags=['review','derived'])
        self.child=self.f.consolidation.consolidate(MemoryRecord.from_dict(body)).memory

    def check_window(self,source,identifier):
        query=ContextSourceQuery('window',self.f.subject_id,'TEST',0,self.f.now,
            purpose=(),query_terms=('review','derived'),limit=1)
        first=source.retrieve(query)
        self.assertEqual([x.stable_id for x in first.candidates],[identifier])
        self.f.service.submit(self.f.command(self.parent.memory_id,'downweight',factor=.1))
        second=source.retrieve(query)
        self.assertEqual([x.stable_id for x in second.candidates],[identifier])
        self.assertAlmostEqual(second.candidates[0].relevance,first.candidates[0].relevance*.1)
        self.assertFalse(source.revalidate(query,first.candidates[0],first.source_version).valid,
                         'unchanged alias hash cannot validate an old full-weight candidate')

    def test_memory_window_weight_drift_without_identity_or_order_change(self):
        self.check_window(MemoryContextSource(self.f.repository,environment='TEST'),self.child.memory_id)

    def test_summary_window_weight_drift_without_identity_or_order_change(self):
        summary=self.f.consolidation.generate_summary(self.f.subject_id,summary_id='weight-summary',
            summary_type='review.window',scope='review:window',source_memory_ids=[self.child.memory_id],confidence=.8)
        self.check_window(DerivedSummaryContextSource(self.f.repository,environment='TEST'),summary.summary_id)


if __name__=='__main__': unittest.main(verbosity=2)
