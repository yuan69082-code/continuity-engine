"""P10-authorized P08 TEST path repair: rejection must precede every write."""
import hashlib
import os
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

from continuity_engine.testing import p08_action_fixture as fixture
from continuity_engine.testing.models import SandboxOperationError


def inventory(root):
    return {p.relative_to(root).as_posix(): ('directory' if p.is_dir() else
            hashlib.sha256(p.read_bytes()).hexdigest())
            for p in root.rglob('*') if not p.is_symlink() and not getattr(p, 'is_junction', lambda: False)()}


class P08FixturePathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='p08-path-review-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        (self.repo / '.git').mkdir()
        (self.repo / 'canary.txt').write_text('synthetic unchanged canary', encoding='utf-8')
        self.module = self.repo / 'src/continuity_engine/testing/p08_action_fixture.py'

    def reject_without_writes(self, target, constructor=fixture.FakeActionAdapter):
        before = inventory(self.root)
        rejected = False
        with patch.object(fixture, 'atomic_write_json', wraps=fixture.atomic_write_json) as writer:
            try:
                constructor(target)
            except SandboxOperationError:
                rejected = True
        self.assertEqual((rejected, writer.call_count, inventory(self.root) == before),
                         (True, 0, True), 'must reject before any directory/file/receipt write')

    def test_repository_under_actual_temp_rejected_without_writes(self):
        with patch.object(fixture, '__file__', str(self.module)):
            self.reject_without_writes(self.repo)

    def test_formal_root_under_temp_repository_rejected_without_writes(self):
        with patch.object(fixture, '__file__', str(self.module)):
            self.reject_without_writes(self.repo / '.continuity-data')

    def test_repository_descendant_rejected_without_writes(self):
        with patch.object(fixture, '__file__', str(self.module)):
            self.reject_without_writes(self.repo / 'missing' / 'fixture')

    def test_repository_ancestor_overlap_rejected_without_writes(self):
        with patch.object(fixture, '__file__', str(self.module)):
            self.reject_without_writes(self.root)

    def test_full_p08_fixture_checks_before_upstream_initialization(self):
        with patch.object(fixture, '__file__', str(self.module)):
            self.reject_without_writes(self.repo, fixture.P08Fixture)

    def test_cwd_repository_with_installed_fixture_rejected_without_writes(self):
        with patch.object(Path, 'cwd', return_value=self.repo):
            self.reject_without_writes(self.repo / '.continuity-data')

    def test_other_repository_with_git_file_rejected_without_writes(self):
        other = self.root / 'other-repository'
        other.mkdir()
        (other / '.git').write_text('gitdir: synthetic-unused', encoding='utf-8')
        self.reject_without_writes(other / 'nested')

    def test_reserved_formal_data_roots_outside_repository_rejected_without_writes(self):
        for name in ('.continuity-data', '.assistant-data'):
            with self.subTest(name=name):
                self.reject_without_writes(self.root / name / 'nested')

    def test_repository_outside_temp_rejected_without_writes(self):
        isolated_temp = self.root / 'os-temp'
        isolated_temp.mkdir()
        with patch.object(fixture.tempfile, 'gettempdir', return_value=str(isolated_temp)), \
                patch.object(fixture, '__file__', str(self.module)):
            self.reject_without_writes(self.repo)

    def test_legal_sibling_temp_fixture_and_reopen_preserve_receipts(self):
        with patch.object(fixture, '__file__', str(self.module)):
            adapter = fixture.FakeActionAdapter(self.root / 'independent-fixture')
            self.assertEqual(adapter.effect_count, 0)
            before = inventory(self.root)
            self.assertEqual(fixture.FakeActionAdapter(adapter.path.parent).receipts(), ())
            self.assertEqual(inventory(self.root), before)

    def test_legal_fixture_with_repository_outside_temp(self):
        isolated_temp = self.root / 'os-temp'
        isolated_temp.mkdir()
        with patch.object(fixture.tempfile, 'gettempdir', return_value=str(isolated_temp)), \
                patch.object(fixture, '__file__', str(self.module)):
            adapter = fixture.FakeActionAdapter(isolated_temp / 'independent-fixture')
            self.assertEqual(adapter.receipts(), ())

    def test_temp_root_itself_rejected_without_writes(self):
        with patch.object(fixture.tempfile, 'gettempdir', return_value=str(self.root)):
            self.reject_without_writes(self.root)

    def test_symlink_component_rejected_without_writes(self):
        target = self.root / 'link-target'
        target.mkdir()
        link = self.root / 'link'
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError as exc:
            self.skipTest('OS does not grant symlink creation: ' + str(exc.winerror if os.name == 'nt' else exc.errno))
        self.addCleanup(link.unlink)
        self.reject_without_writes(link / 'fixture')

    def test_reparse_component_rejected_without_writes(self):
        target = self.root / 'reparse'
        target.mkdir()
        from continuity_engine.testing import persistence
        original = persistence.is_link_like
        with patch.object(persistence, 'is_link_like', side_effect=lambda p: p == target or original(p)):
            self.reject_without_writes(target / 'fixture')

    def test_explicit_formal_and_protected_overlaps_rejected_without_writes(self):
        protected = self.root / 'owner-domain' / 'state'
        for keyword in ('formal_data_roots', 'protected_paths'):
            for target in (protected, protected / 'nested', protected.parent):
                for factory in (fixture.FakeActionAdapter, fixture.P08Fixture):
                    with self.subTest(keyword=keyword, target=target, factory=factory.__name__):
                        self.reject_without_writes(target, lambda p: factory(p, **{keyword: (protected,)}))

    def test_parent_of_existing_formal_root_rejected_without_writes(self):
        parent = self.root / 'owner'
        (parent / '.continuity-data').mkdir(parents=True)
        self.reject_without_writes(parent)

    def test_receipt_reparse_point_rejected_without_writes(self):
        parent = self.root / 'receipt-link'
        parent.mkdir()
        receipt = parent / 'p08-fake-receipts.json'
        receipt.write_text('synthetic reparse canary', encoding='utf-8')
        from continuity_engine.testing import persistence
        original = persistence.is_link_like
        with patch.object(persistence, 'is_link_like', side_effect=lambda p: p == receipt or original(p)):
            self.reject_without_writes(parent)

    @unittest.skipUnless(os.name == 'nt', 'Windows junction regression')
    def test_real_windows_junction_rejected_without_writes(self):
        target = self.root / 'junction-target'
        target.mkdir()
        link = self.root / 'junction'
        result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(target)], capture_output=True)
        self.assertEqual(result.returncode, 0, 'isolated test junction must be created')
        self.addCleanup(link.rmdir)
        self.reject_without_writes(link / 'fixture')


class P08ReservedDirectoryCaseTests(unittest.TestCase):
    """Real platform paths, including samefile proof on Windows, not string mocks."""

    def setUp(self):
        P08FixturePathTests.setUp(self)

    def check_spellings(self, transform, *, child, alias=False):
        for index, (name, factory) in enumerate(
                (name, factory) for name in ('.continuity-data', '.assistant-data')
                for factory in (fixture.FakeActionAdapter, fixture.P08Fixture)):
            with self.subTest(name=name, factory=factory.__name__, child=child, alias=alias):
                # Numeric owners avoid Windows setup collisions between case variants.
                owner = self.root / ('case-' + str(index) + ('-child' if child else '-root'))
                reserved = owner / transform(name)
                reserved.mkdir(parents=True)
                canary = reserved / 'synthetic-canary.txt'
                canary.write_text('TEST ONLY - unchanged', encoding='utf-8')
                canonical = owner / name
                if os.name == 'nt':
                    self.assertTrue(reserved.samefile(canonical))
                target = canonical if alias else reserved
                if child:
                    target = target / 'new-test-child'
                if os.name == 'nt' or transform(name) == name:
                    P08FixturePathTests.reject_without_writes(self, target, factory)
                else:
                    # On a case-sensitive POSIX filesystem the differently named
                    # directory is not the reserved lower-case path; keep it usable.
                    self.assertFalse(canonical.exists())
                    instance = factory(target)
                    adapter = instance if factory is fixture.FakeActionAdapter else instance.adapter
                    self.assertEqual(adapter.receipts(), ())
                    self.assertEqual(canary.read_text(encoding='utf-8'), 'TEST ONLY - unchanged')

    def test_uppercase_directory_itself_follows_platform_semantics(self):
        self.check_spellings(str.upper, child=False)

    def test_uppercase_directory_child_follows_platform_semantics(self):
        self.check_spellings(str.upper, child=True)

    def test_mixedcase_directory_itself_follows_platform_semantics(self):
        self.check_spellings(str.title, child=False)

    def test_mixedcase_directory_child_follows_platform_semantics(self):
        self.check_spellings(str.title, child=True)

    def test_lowercase_directory_and_child_controls_are_zero_write(self):
        self.check_spellings(str.lower, child=False)
        self.check_spellings(str.lower, child=True)

    @unittest.skipUnless(os.name == 'nt', 'Windows samefile aliases')
    def test_lowercase_alias_of_uppercase_directory_is_zero_write(self):
        self.check_spellings(str.upper, child=False, alias=True)
        self.check_spellings(str.upper, child=True, alias=True)


if __name__ == '__main__':
    unittest.main()
