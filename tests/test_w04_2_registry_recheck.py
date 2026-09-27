"""Current-file boundary regression for the shared P16/W02 registry read path."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from continuity_engine.domain.external_capabilities import ExternalCapabilityError
from continuity_engine.testing.w02_c_fixture import W02CFixture


class RegistryCurrentPathTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='w4-registry-')
        self.addCleanup(self.temp.cleanup)
        self.f=W02CFixture(Path(self.temp.name))
        self.repository=self.f.base.registry

    def test_current_registry_repeated_read_is_read_only_and_returns_private_values(self):
        r=self.repository;before=r.registry_path.read_bytes()
        first=r._read('registry');first['entries'].clear()
        self.assertTrue(r._read('registry')['entries'])
        self.assertEqual(r.registry_path.read_bytes(),before)

    def test_registry_revoke_is_seen_on_next_read_and_after_reopen(self):
        r=self.repository;d,enabled=r.descriptors()[0];self.assertTrue(enabled)
        r.disable(d.key,expected_revision=r.revision)
        self.assertFalse(r.get(d.key)[1])
        self.f.reopen();self.assertFalse(self.f.base.registry.get(d.key)[1])

    def test_changed_bytes_and_corrupt_hash_cannot_reuse_old_registry(self):
        r=self.repository;r.descriptors();document=json.loads(r.registry_path.read_text(encoding='utf8'))
        document['document']['revision']+=1
        r.registry_path.write_text(json.dumps(document),encoding='utf8')
        before=r.registry_path.read_bytes()
        with self.assertRaisesRegex(ExternalCapabilityError,'EXTERNAL_STORE_CORRUPT'):r.descriptors()
        self.assertEqual(r.registry_path.read_bytes(),before)

    def test_missing_store_still_has_no_capability(self):
        from continuity_engine.storage.json_external_provider_repository import JsonExternalProviderRepository
        r=JsonExternalProviderRepository(Path(self.temp.name)/'missing',subject_id='subject:none',environment='TEST')
        self.assertEqual(r.descriptors(),())
        self.assertFalse(r.root.exists())

    def test_current_directory_junction_rejects_and_restoring_real_directory_recovers(self):
        # Native NT junction in TEST, no symlink privilege or formal root.
        r=self.repository;original=r.root;parked=original.with_name(original.name+'-parked')
        before=r.registry_path.read_bytes();original.rename(parked)
        try:
            if os.name=='nt':
                import _winapi
                _winapi.CreateJunction(str(parked),str(original))
            else:original.symlink_to(parked,target_is_directory=True)
            with self.assertRaisesRegex(ExternalCapabilityError,'EXTERNAL_STORE_LINK_FORBIDDEN'):r.descriptors()
        finally:
            if original.is_symlink():original.unlink()
            elif getattr(original,'is_junction',lambda:False)():original.rmdir()
            parked.rename(original)
        self.assertTrue(r.descriptors());self.assertEqual(r.registry_path.read_bytes(),before)

    def test_path_metadata_denial_is_not_a_successful_read(self):
        # No ACL mutation: inject the OS metadata refusal at the path port.
        from continuity_engine.storage.json_external_provider_repository import JsonExternalProviderRepository
        r=self.repository;before=r.registry_path.read_bytes()
        from contextlib import ExitStack
        with ExitStack() as stack:
            for name in ('is_symlink','exists','is_junction','lstat'):
                if not hasattr(Path,name):continue
                old=getattr(Path,name)
                def denied(p,*a,_old=old,**kw):
                    if p==r.root:raise PermissionError(13,'TEST_METADATA_DENIED')
                    return _old(p,*a,**kw)
                stack.enter_context(patch.object(Path,name,denied))
            with self.assertRaises(PermissionError):JsonExternalProviderRepository._safe(r.registry_path)
        self.assertEqual(r.registry_path.read_bytes(),before)

    def test_recheck_all_current_ancestors_on_each_read_with_single_metadata_query(self):
        # Bounded I/O assertion, not elapsed-time tuning: no repeated probes of
        # one ancestor within a check, and no skipping checks on a later read.
        from continuity_engine.storage.json_external_provider_repository import JsonExternalProviderRepository
        r=self.repository;calls=[];depth=[0]
        from contextlib import ExitStack
        original_safe=JsonExternalProviderRepository._safe
        active=[False]
        def safe(p):
            active[0]=True
            try:return original_safe(p)
            finally:active[0]=False
        with ExitStack() as stack:
            stack.enter_context(patch.object(JsonExternalProviderRepository,'_safe',staticmethod(safe)))
            for name in ('is_symlink','exists','is_junction','lstat'):
                if not hasattr(Path,name):continue
                original=getattr(Path,name)
                def observed(p,*a,_original=original,**kw):
                    if active[0] and not depth[0]:calls.append(p)
                    depth[0]+=1
                    try:return _original(p,*a,**kw)
                    finally:depth[0]-=1
                stack.enter_context(patch.object(Path,name,observed))
            r.descriptors();split=len(calls);r.descriptors()
        expected=[r.registry_path,*r.registry_path.parents]
        self.assertEqual(calls[:split],expected)
        self.assertEqual(calls[split:],expected)

if __name__=='__main__':unittest.main()
