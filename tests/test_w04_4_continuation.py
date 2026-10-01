"""Versioned TEST messages through original C1 and native runtime controls."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from continuity_engine.testing.w04_cross_entry_fixture import W04EntryFixture
from continuity_engine.testing.w02_input_fixture import capture_failure
from continuity_engine.domain.errors import IntegrationExecutionError


class ContinuationTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory(prefix='w44-continue-')
        self.f=W04EntryFixture(Path(self.temp.name))
    def tearDown(self):
        capture_failure(self,Path(self.temp.name)); self.temp.cleanup()

    def test_same_user_two_matters_and_ambiguous_reference_stay_separate(self):
        f=self.f; f.submit('周六选河边店还是山坡店？')
        one=f.entries.adopt_matter(f.last_request['requestId']);f.advance()
        f.submit('文稿选蓝色封面还是绿色封面？')
        two=f.entries.adopt_matter(f.last_request['requestId']);f.advance()
        self.assertNotEqual(one.item_id,two.item_id)
        result=f.submit('那件事怎么样了？',entry='entry:B')
        self.assertIn('你指的是哪件事',result.response.content)
        self.assertEqual({r['item_id'] for r in f.state.continuity.item_records},{one.item_id,two.item_id})
        self.assertIsNone(f.entries.inspect(f.last_request['requestId'])['item_id'])

    def test_late_timezone_message_preserves_three_times_and_mirror_root(self):
        f=self.f; request,message=f.message('迟到的会议材料。')
        now=f.runtime.clock.now()
        message=replace(message,occurred_at=(now-timedelta(days=1)).astimezone(__import__('datetime').timezone(timedelta(hours=8))).isoformat(),
            observed_at=(now-timedelta(minutes=2)).isoformat(),uncertainty_seconds=15)
        result=f.entries.receive(request,message); self.assertEqual(result.status,'completed')
        view=f.entries.inspect(request['requestId'])['source']
        for key in ('occurred_at','observed_at','recorded_at','uncertainty_seconds'):
            self.assertEqual(view[key],getattr(message,key))
        duplicate,mirror=f.message('迟到的会议材料。',entry='entry:B',mirror_of=request['requestId'])
        before=(len(f.provider.inputs),f.state.revision)
        self.assertEqual(f.entries.receive(duplicate,mirror)['root_request_id'],request['requestId'])
        self.assertEqual((len(f.provider.inputs),f.state.revision),before)

    def test_concurrent_a_b_requests_remain_bound_without_duplicate_effects(self):
        f=self.f; a=f.message('A的并发材料。');b=f.message('B的并发材料。',entry='entry:B')
        start=threading.Barrier(2)
        def receive(pair):
            start.wait(5)
            try:return f.entries.receive(*pair)
            except IntegrationExecutionError as exc:return exc
            except __import__('continuity_engine.domain.errors',fromlist=['CapabilityValidationError']).CapabilityValidationError as exc:
                if str(exc) != 'INPUT_ADMISSION_BUSY':raise
                self.assertIsNone(f.app.ledger.load_operation(pair[0]['requestId']))
                return exc
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(receive,(a,b)))
        success=[o for o in outcomes if getattr(o,'status',None)=='completed']
        self.assertGreaterEqual(len(success),1)
        for request,message in (a,b):
            operation=f.app.ledger.load_operation(request['requestId'])
            if operation is not None:
                self.assertEqual(operation.entry_record['message']['entry_id'],message.entry_id)
        self.assertEqual(sum(p.effect_count for p in f.ports.values()),len(success))
        self.assertEqual(sum(p.credits for p in f.ports.values()),len(success))
        for pair,outcome in zip((a,b),outcomes):
            if str(outcome)=='INPUT_ADMISSION_BUSY':
                self.assertEqual(f.entries.receive(*pair).status,'completed')
        self.assertEqual(sum(p.effect_count for p in f.ports.values()),2)
        self.assertEqual(len({o.subject_id for o in f.app.ledger.list_operations()}),1)

    def test_loss_after_effect_reopens_original_thinking_and_send(self):
        f=self.f; fired=[]
        def fault(stage,operation):
            if stage=='after_c1_action_completed' and not fired:
                fired.append(True);raise OSError('TEST lost C1 checkpoint return')
        f.app.adapter.service._fault_injector=fault
        with self.assertRaises(IntegrationExecutionError):f.submit('原发送回执不可重复。')
        self.assertTrue(fired);self.assertEqual(f.ports['entry:A'].effect_count,1)
        request,message=f.last_request,f.last_message
        f.reopen();result=f.entries.receive(request,message)
        self.assertEqual(result.status,'completed')
        self.assertEqual(f.provider.inputs,[])
        self.assertEqual((f.ports['entry:A'].effect_count,f.ports['entry:A'].credits),(1,1))

    def test_owner_pause_stop_and_silent_native_work_do_not_send(self):
        f=self.f;f.start_native()
        def control(op):
            return f.host.control(op,command_id='control:'+op,expected_revision=None,handle='p18-test-owner')
        with f.host.running():
            control('PAUSE');f.runtime.clock.advance(timedelta(minutes=15));f.host.tick()
            self.assertEqual(len(f.provider.inputs),0)
            control('RESUME')
            from continuity_engine.domain.persistent_runtime import parse
            for _ in range(8):
                f.host.tick()
                if f.provider.inputs:break
                due=f.host.query()['next_check_at']
                f.runtime.clock.advance(timedelta(seconds=max(1,(parse(due)-f.runtime.clock.now()).total_seconds()) if due else 1))
            self.assertGreater(len(f.provider.inputs),0)
            self.assertEqual(sum(p.effect_count for p in f.ports.values()),0)
            control('STOP');self.assertFalse(f.host.tick())
        with f.host.running():self.assertFalse(f.host.tick())
        from continuity_engine.domain.persistent_runtime import RuntimeBoundaryError
        control('RESUME')  # Replaying an OLD accepted command is no new command.
        self.assertEqual(f.host.query()['desired'],'STOPPED')
        with self.assertRaises(RuntimeBoundaryError):
            f.host.control('RESUME',command_id='control:RESUME-after-stop',expected_revision=None,handle='p18-test-owner')


if __name__=='__main__':unittest.main()
