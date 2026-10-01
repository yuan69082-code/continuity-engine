"""Single heavy diagnostic; timing includes profiler and is not acceptance."""
import cProfile,io,pstats,unittest
from continuity_engine.testing.w04_cross_entry_fixture import W04EntryFixture
from tests.test_w04_package import W04PackageTests
original=W04EntryFixture.submit
def submit(self,text,**kw):
    if text!='周六选河边店还是山坡店？':return original(self,text,**kw)
    prepare=self.core.recall._prepare
    def measured(*a,**k):
        profile=cProfile.Profile();profile.enable()
        try:return prepare(*a,**k)
        finally:
            profile.disable()
            stats=pstats.Stats(profile).strip_dirs()
            stats.sort_stats('tottime').print_stats(35)
            stats.sort_stats('cumulative').print_stats(45)
    self.core.recall._prepare=measured
    return original(self,text,**kw)
W04EntryFixture.submit=submit
result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName(
    'tests.test_w04_package.W04PackageTests.test_discovery_history_body_and_native_cross_entry_share_authorities'))
raise SystemExit(not result.wasSuccessful())
