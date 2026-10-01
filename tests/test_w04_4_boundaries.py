"""W04-4 additional real-entry boundaries; no original tests changed."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from continuity_engine.testing.w04_cross_entry_fixture import W04EntryFixture
from continuity_engine.domain.errors import IntegrationExecutionError
from continuity_engine.domain.environment_access import EnvironmentAccessError

class EntryBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix='w44-boundary-')
        self.f = W04EntryFixture(Path(self.temp.name))
    def tearDown(self):
        from continuity_engine.testing.w02_input_fixture import capture_failure
        capture_failure(self, Path(self.temp.name))
        self.temp.cleanup()

    def test_group_bound_recipient_success_wrong_group_and_self_sender_rejected(self):
        self.f.configure('entry:A', audience='GROUP', recipient_account='group:friends')
        request, message = self.f.message('今晚聚餐在哪里？')
        message = replace(message, recipient_account='group:friends')
        for bad in (replace(message, recipient_account='group:other'),
                    replace(message, sender_account='subject-account:A')):
            with self.assertRaises(IntegrationExecutionError):
                self.f.entries.receive(request, bad)
        self.assertIsNone(self.f.app.ledger.load_operation(request['requestId']))
        self.assertEqual(self.f.entries.receive(request, message).status, 'completed')
        self.assertEqual(self.f.ports['entry:A'].effect_count, 1)

    def test_read_callback_binding_change_is_rejected_before_persistence(self):
        request, message = self.f.message('当前授权才可入站。')
        def read(binding):
            prior = self.f.repo.load()
            changed = replace(binding, version=binding.version+1, can_receive=False)
            self.f.repo.bind_entry(changed, expected_revision=prior['revision'])
            return True
        self.f.entries.authorize_read = read
        with self.assertRaises(IntegrationExecutionError):
            self.f.entries.receive(request, message)
        self.assertIsNone(self.f.app.ledger.load_operation(request['requestId']))
        self.assertEqual(self.f.ports['entry:A'].effect_count, 0)

    def test_unknown_old_send_does_not_freeze_distinct_same_matter_inquiry(self):
        self.f.submit('周六选河边店还是山坡店？')
        item = self.f.entries.adopt_matter(self.f.last_request['requestId'])
        self.f.ports['entry:B'].mode = 'unknown'
        self.f.advance()
        try:
            self.f.submit('周六还是这个选店问题？', entry='entry:A', item_id=item.item_id, preferred_entry_id='entry:B')
        except IntegrationExecutionError:
            pass
        old_id = self.f.last_request['requestId']
        old = self.f.entries.inspect(old_id)['deliveries'][0]
        self.assertEqual(old['status'], 'UNKNOWN')
        self.assertEqual(self.f.ports['entry:B'].effect_count, 0)
        prior_query = self.f.ports['entry:B'].query
        old_cap = old['request_id']
        self.f.ports['entry:B'].mode = 'success'
        from continuity_engine.domain.action_capability import ReceiptQuery
        self.f.ports['entry:B'].query = lambda request: ReceiptQuery.UNKNOWN if request.capability_request_id == old_cap else prior_query(request)
        self.f.advance()
        outcome = self.f.submit('周六还是这个选店问题？', entry='entry:A', item_id=item.item_id, preferred_entry_id='entry:B')
        self.assertEqual(outcome.status, 'completed')
        self.assertEqual(self.f.ports['entry:B'].effect_count, 1)
        self.assertEqual(self.f.ports['entry:B'].credits, 1)
        self.assertEqual(self.f.entries.inspect(old_id)['deliveries'][0]['status'], 'UNKNOWN')
        self.assertNotEqual(self.f.last_request['requestId'], old_id)

    def test_dispatched_unknown_send_allows_distinct_inquiry_without_replaying_original(self):
        self.f.submit('周六选河边店还是山坡店？')
        item = self.f.entries.adopt_matter(self.f.last_request['requestId'])
        self.f.ports['entry:B'].mode = 'unobservable_after'
        self.f.advance()
        try:
            self.f.submit('周六还是这个选店问题？', entry='entry:A', item_id=item.item_id, preferred_entry_id='entry:B')
        except IntegrationExecutionError:
            pass
        old_id = self.f.last_request['requestId']
        old = self.f.entries.inspect(old_id)['deliveries'][0]
        self.assertEqual(old['status'], 'UNKNOWN')
        self.assertEqual(self.f.ports['entry:B'].effect_count, 1)
        prior_query = self.f.ports['entry:B'].query
        old_cap = old['request_id']
        self.f.ports['entry:B'].mode = 'success'
        from continuity_engine.domain.action_capability import ReceiptQuery
        self.f.ports['entry:B'].query = lambda request: ReceiptQuery.UNKNOWN if request.capability_request_id == old_cap else prior_query(request)
        self.f.advance()
        outcome = self.f.submit('周六还是这个选店问题？', entry='entry:A', item_id=item.item_id, preferred_entry_id='entry:B')
        self.assertEqual(outcome.status, 'completed')
        self.assertEqual(self.f.ports['entry:B'].effect_count, 2)
        self.assertEqual(self.f.ports['entry:B'].credits, 2)
        self.assertEqual(self.f.entries.inspect(old_id)['deliveries'][0]['status'], 'UNKNOWN')
        self.assertNotEqual(self.f.last_request['requestId'], old_id)

    def test_native_unknown_delivery_does_not_prevent_later_cognition(self):
        self.f.submit('周六选河边店还是山坡店？')
        self.f.entries.adopt_matter(self.f.last_request['requestId'])
        self.f.ports['entry:B'].mode = 'unobservable_after'
        try:
            self.f.continue_native()
        except AssertionError:
            pass
        first_count = len(self.f.provider.inputs)
        self.assertEqual(self.f.ports['entry:B'].effect_count, 1)
        try:
            self.f.continue_native()
        except AssertionError:
            pass
        import sys
        print(json.dumps({'stage': 'before-TEST-cleanup', 'first_calls': first_count,
            'after_calls': len(self.f.provider.inputs), 'host': self.f.host.query(),
            'tasks': [{'id': t.task_id, 'state': t.state.value, 'attempts': t.attempt_count}
                for t in self.f.scheduler.list_tasks(subject_id=self.f.state.subject_id, environment='TEST')],
            'effects': self.f.ports['entry:B'].effect_count, 'credits': self.f.ports['entry:B'].credits,
            'revision': self.f.state.revision}), file=sys.stderr)
        self.assertGreater(len(self.f.provider.inputs), first_count)

    def test_native_history_does_not_bypass_later_entry_transfer_withdrawal(self):
        private = 'A_PRIVATE_TABLE_749'
        self.f.submit(private + '选哪家店？')
        self.f.entries.adopt_matter(self.f.last_request['requestId'])
        self.f.continue_native()
        self.f.native_mode = False
        self.f.reopen()
        self.f.configure('entry:B', read_from=('entry:B',))
        self.f.advance()
        result = self.f.submit('B本地独立的工程事项。', entry='entry:B')
        self.assertEqual(result.status, 'completed')
        fragments = self.f.provider.inputs[-1].continuity_context.composition.snapshot.fragments
        self.assertNotIn(private, '\n'.join(fragment.content for fragment in fragments))
        self.assertIn('B本地独立的工程事项。', result.response.content)

    def test_related_native_memory_cannot_bypass_entry_transfer_withdrawal(self):
        private = '河边秘密餐馆代号749'
        self.f.submit(private + '选哪家店？')
        self.f.entries.adopt_matter(self.f.last_request['requestId'])
        self.f.continue_native()
        self.f.native_mode = False
        self.f.reopen()
        self.f.configure('entry:B', read_from=('entry:B',))
        self.f.advance()
        result = self.f.submit('河边餐馆有什么旧资料。', entry='entry:B')
        self.assertEqual(result.status, 'completed')
        fragments = self.f.provider.inputs[-1].continuity_context.composition.snapshot.fragments
        self.assertNotIn(private, '\n'.join(fragment.content for fragment in fragments))
        self.assertIn('河边餐馆有什么旧资料。', result.response.content)

    def test_scoped_state_parse_checks_current_bytes_and_returns_private_copies(self):
        from continuity_engine.domain.errors import StateValidationError
        repository = self.f.runtime.subject_states._repository
        subject = self.f.state.subject_id
        path = repository._path_for(subject)
        before = path.read_bytes()
        with repository._verified_state_reads():
            state = repository.load(subject)
            state.continuity.unfinished_items.append('not persistent')
            self.assertNotIn('not persistent', repository.load(subject).continuity.unfinished_items)
            path.write_bytes(before[:-1] + b'!')
            with self.assertRaises(StateValidationError):
                repository.load(subject)
            path.write_bytes(before)
            self.assertEqual(repository.load(subject).subject_id, subject)

    def test_environment_callback_changes_cannot_pass_single_document_reuse(self):
        use = self.f.entries.binding('entry:A').use
        previous = self.f.access.authorize
        def revoke(attachment, **kw):
            self.f.repo.disable(attachment.attachment_id, expected_revision=self.f.repo.load()['revision'])
            return True
        self.f.access.authorize = revoke
        with self.assertRaisesRegex(EnvironmentAccessError, 'CHANGED_DURING_CHECK'):
            self.f.entries.binding('entry:A')
        self.f.access.authorize = previous

    def test_contact_pause_does_not_cancel_independent_native_mind_update(self):
        self.f.submit('周六选河边店还是山坡店？')
        self.f.entries.adopt_matter(self.f.last_request['requestId'])
        self.f.entries.pause_contact('entry:A', True, expected_revision=self.f.repo.load()['revision'])
        revision = self.f.state.revision
        self.f.continue_native()
        self.assertGreater(self.f.state.revision, revision)
        self.assertEqual((self.f.ports['entry:B'].effect_count, self.f.ports['entry:B'].credits), (0, 0))

    def test_transfer_revoked_inside_read_callback_does_not_return_old_grant(self):
        self.f.submit('仅在当前授权下转用的资料。')
        fired = []
        def change(binding):
            if binding.entry_id == 'entry:B' and not fired:
                fired.append(True)
                self.f.configure('entry:B', read_from=('entry:B',))
            return True
        self.f.entries.authorize_read = change
        before = sum(port.effect_count for port in self.f.ports.values())
        with self.assertRaisesRegex(EnvironmentAccessError, 'BINDING_CHANGED_DURING_CHECK'):
            self.f.entries.transfer('entry:A', 'entry:B')
        self.assertEqual(sum(port.effect_count for port in self.f.ports.values()), before)
        self.f.entries.authorize_read = lambda binding: True
        self.assertFalse(self.f.entries.transfer('entry:A', 'entry:B'))
        self.f.reopen()
        self.assertFalse(self.f.entries.transfer('entry:A', 'entry:B'))

    def test_thinking_projection_reads_current_bytes_and_returns_private_copies(self):
        from continuity_engine.domain.errors import ThinkingValidationError
        self.f.submit('原始材料的合法正常使用。')
        repository = self.f.entries.native_thinking._repository
        session = repository.list_think_sessions(self.f.state.subject_id)[0]
        path = repository._path(session.subject_id, session.think_id)
        raw = path.read_bytes()
        with repository._verified_session_reads():
            project = lambda value: value.to_dict()
            first = repository._load_projection(session.subject_id, session.think_id, project)
            first['subject_id'] = 'not-persisted'
            self.assertEqual(repository._load_projection(session.subject_id, session.think_id, project)['subject_id'], session.subject_id)
            path.write_bytes(raw[:-1] + b'!')
            with self.assertRaises(ThinkingValidationError):
                repository._load_projection(session.subject_id, session.think_id, project)
            path.write_bytes(raw)
            self.assertEqual(repository._load_projection(session.subject_id, session.think_id, project), session.to_dict())

    def test_capability_projection_validates_unselected_records_and_isolates_copies(self):
        from continuity_engine.domain.errors import IntegrationPersistenceError
        self.f.submit('原账本保持全部事实。')
        repository = self.f.app.ledger
        path = repository._capability_path
        raw = path.read_bytes()
        request = repository._load_capability_document()[0][0]
        with repository._verified_capability_reads():
            selected = repository.load_capability_request(request.capability_request_id)
            self.assertEqual(selected, request)
            # Mutable projected containers must not be aliases of the scope.
            first = repository._load_capability_document(_projection=lambda r, a: [x.to_dict() for x in r])
            first.clear()
            self.assertTrue(repository._load_capability_document(_projection=lambda r, a: [x.to_dict() for x in r]))
            bad = json.loads(raw)
            bad['requests'].append({'not': 'a valid unrelated request'})
            path.write_text(json.dumps(bad), encoding='utf8')
            with self.assertRaises(IntegrationPersistenceError):
                repository.load_capability_request(request.capability_request_id)
            path.write_bytes(raw)
            self.assertEqual(repository.load_capability_request(request.capability_request_id), request)

    def test_digest_scope_recomputes_mutations_and_keeps_rfc_rejections(self):
        from continuity_engine.domain.action_planning import digest,verified_digest_reads
        from continuity_engine.domain.integration_hashing import canonicalize_json,sha256_hash
        from continuity_engine.domain.errors import MachineContractValidationError
        values=[None,True,1,1.0,-0.0,{'x':['中文',1,{'active':True}]},['a',2]]
        expected=[sha256_hash(canonicalize_json(value)) for value in values]
        with verified_digest_reads():
            self.assertEqual([digest(v) for v in values],expected)
            self.assertEqual([digest(v) for v in values],expected)
            value=values[5];before=digest(value);value['x'][2]['active']=False
            self.assertNotEqual(digest(value),before)
            self.assertEqual(digest(value),sha256_hash(canonicalize_json(value)))
            for bad in ({1:'a'},float('nan'),float('inf'),2**80):
                with self.assertRaises(MachineContractValidationError):digest(bad)
        self.assertEqual(digest(value),sha256_hash(canonicalize_json(value)))

    def _entry_history_query(self):
        f=self.f;f.submit('A原入口的历史记录。')
        send=f.entries.inspect(f.last_request['requestId'])['deliveries'][0]['request_id']
        row=f.delivery_notice('entry:A',send,'READ')
        marker='A_QUERY_PRIVATE_957'
        f.ports['entry:A'].change(history=[{**row,'content':marker}])
        query=f.query_delivery('entry:A',send,'query:entry-source')
        return marker,query

    def test_ui_history_result_cannot_bypass_entry_transfer_withdrawal(self):
        marker,query=self._entry_history_query()
        self.f.configure('entry:B',read_from=('entry:B',));self.f.reopen();self.f.advance()
        result=self.f.submit('B本地的历史查询材料。',entry='entry:B')
        self.assertEqual(result.status,'completed')
        fragments=self.f.provider.inputs[-1].continuity_context.composition.snapshot.fragments
        self.assertNotIn(marker,'\n'.join(row.content for row in fragments))
        self.assertFalse(any(row.stable_source_id=='execution:'+query.capability_request_id for row in fragments))
        self.assertEqual((self.f.ports['entry:A'].effect_count,self.f.ports['entry:A'].credits),(1,1))

    def test_authorized_ui_history_result_is_available_without_new_query_cost(self):
        marker,query=self._entry_history_query();self.f.reopen();self.f.advance()
        result=self.f.submit('B获准使用的历史查询材料。',entry='entry:B')
        self.assertEqual(result.status,'completed')
        fragments=self.f.provider.inputs[-1].continuity_context.composition.snapshot.fragments
        self.assertIn(marker,'\n'.join(row.content for row in fragments))
        self.assertTrue(any(row.stable_source_id=='execution:'+query.capability_request_id for row in fragments))
        self.assertEqual((self.f.ports['entry:A'].effect_count,self.f.ports['entry:A'].credits),(1,1))

    def test_native_new_inquiry_can_send_when_original_remains_unknown(self):
        from continuity_engine.domain.action_capability import ReceiptQuery
        f=self.f;f.submit('周六选河边店还是山坡店？');f.entries.adopt_matter(f.last_request['requestId'])
        port=f.ports['entry:B'];port.mode='unobservable_after'
        first=f.continue_native();old=f.entries.inspect(first)['deliveries'][0]
        self.assertEqual(old['status'],'UNKNOWN');self.assertEqual(port.effect_count,1)
        native_query=port.query;port.mode='success'
        port.query=lambda request:ReceiptQuery.UNKNOWN if request.capability_request_id==old['request_id'] else native_query(request)
        second=f.continue_native();new=f.entries.inspect(second)['deliveries'][0]
        self.assertNotEqual(new['request_id'],old['request_id'])
        self.assertEqual(new['status'],'SENT')
        self.assertEqual(f.entries.inspect(first)['deliveries'][0]['status'],'UNKNOWN')
        self.assertEqual((port.effect_count,port.credits),(2,2))

    def test_environment_current_junction_rejects_before_ingress_and_restores(self):
        import os
        directory=self.f.repo.path.parent
        parked=directory.with_name(directory.name+'-parked')
        before=self.f.repo.path.read_bytes()
        request,message=self.f.message('隔离目录检查。')
        directory.rename(parked)
        try:
            if os.name=='nt':
                import _winapi
                _winapi.CreateJunction(str(parked),str(directory))
            else:
                directory.symlink_to(parked,target_is_directory=True)
            with self.assertRaises(IntegrationExecutionError) as rejected:
                self.f.entries.receive(request,message)
            self.assertIsInstance(rejected.exception.__cause__,EnvironmentAccessError)
            self.assertEqual(str(rejected.exception.__cause__),'W04_STORE_LINK_FORBIDDEN')
            self.assertIsNone(self.f.app.ledger.load_operation(request['requestId']))
            self.assertEqual(sum(p.effect_count for p in self.f.ports.values()),0)
        finally:
            # Both exact paths belong to this isolated TEST directory.
            if directory.is_symlink():directory.unlink()
            elif getattr(directory,'is_junction',lambda:False)():directory.rmdir()
            parked.rename(directory)
        self.assertEqual(self.f.repo.path.read_bytes(),before)
        self.assertEqual(self.f.entries.receive(request,message).status,'completed')

    def test_environment_metadata_access_denied_is_not_absent_or_cached(self):
        import os
        from unittest.mock import patch
        from continuity_engine.storage import json_environment_repository as module
        self.f.repo.load()  # Populate only the validated-byte parse.
        before=self.f.repo.path.read_bytes()
        request,message=self.f.message('访问拒绝不能跳过。')
        if os.name=='nt':
            def denied(path):
                module.ctypes.set_last_error(5)
                return 0xffffffff
            with patch.object(module,'_get_attributes',side_effect=denied):
                with self.assertRaises(IntegrationExecutionError) as rejected:self.f.entries.receive(request,message)
            self.assertIsInstance(rejected.exception.__cause__,PermissionError)
            self.assertEqual(rejected.exception.__cause__.winerror,5)
        else:
            with patch.object(module,'_path_is_link',side_effect=PermissionError(13,'denied')):
                with self.assertRaises(IntegrationExecutionError) as rejected:self.f.entries.receive(request,message)
            self.assertIsInstance(rejected.exception.__cause__,PermissionError)
        self.assertIsNone(self.f.app.ledger.load_operation(request['requestId']))
        self.assertEqual(self.f.repo.path.read_bytes(),before)
        self.assertEqual(sum(p.effect_count for p in self.f.ports.values()),0)
        self.assertEqual(self.f.entries.receive(request,message).status,'completed')

    def test_provenance_projection_validates_whole_current_journal_and_isolates(self):
        from continuity_engine.domain.errors import IntegrationPersistenceError
        self.f.submit('原始来源不会成为第二份事实。')
        ledger=self.f.app.ledger;path=ledger._operation_path;raw=path.read_bytes()
        request=self.f.last_request['requestId'];before=self.f.state.revision
        with ledger._verified_operation_reads():
            first=self.f.entries._provenance_operations()
            selected=next(v for v in first if v.request_id==request)
            self.assertEqual(selected.entry_record['message']['entry_id'],'entry:A')
            self.assertTrue(selected.event_ids)
            selected.entry_record['message']['entry_id']='invented'
            self.assertEqual(self.f.entries.origins('engine.current-input','input:'+request),{'entry:A'})
            corrupt=json.loads(raw);corrupt['operations'].append({'unselected':'invalid'})
            path.write_text(json.dumps(corrupt),encoding='utf8')
            with self.assertRaises(IntegrationPersistenceError):self.f.entries._provenance_operations()
            path.write_bytes(raw)
            self.assertEqual(self.f.entries.origins('engine.current-input','input:'+request),{'entry:A'})
        self.assertEqual(self.f.state.revision,before)
        self.assertEqual(path.read_bytes(),raw)

    def test_unknown_body_effect_cannot_masquerade_as_new_contact(self):
        from continuity_engine.domain.action_capability import ReceiptQuery
        f=self.f;f.submit('身体行动只是隔离 TEST。')
        port=f.base.fake;port.mode='unobservable_after'
        old,run=f.prepare_step(f.base.device.step(f.base.command('body.act',amount=1)),'body:unknown')
        self.assertNotEqual(run().status,'COMPLETED');self.assertEqual(port.effect_count,1)
        native_query=port.query;port.mode='success'
        port.query=lambda request:ReceiptQuery.UNKNOWN if request.capability_request_id==old.capability_request_id else native_query(request)
        new,run=f.prepare_step(f.base.device.step(f.base.command('body.act',amount=2)),'body:distinct')
        self.assertFalse(f.entries.independent_inquiry(old,new))
        self.assertNotEqual(run().status,'COMPLETED')
        self.assertEqual((port.effect_count,port.credits),(1,1))

if __name__ == '__main__':
    unittest.main()
