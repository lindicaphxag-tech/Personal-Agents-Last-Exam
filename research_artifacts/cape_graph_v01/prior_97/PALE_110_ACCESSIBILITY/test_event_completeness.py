"""Red-team false positives identified on the signed first-generation pilot.

Mutations are re-signed only with the *test author's* synthetic fixture key,
which is never available to a candidate agent or official PALE runtime.
"""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from route_gate import construct, reference, verify, read, dump, sign_events

class EventCompletenessRedTeam(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory()
        root=Path(self.temp.name)
        self.public,self.hidden,self.output=root/'public',root/'hidden',root/'out'
        construct(self.public,self.hidden)
        reference(self.public,self.hidden,self.output)

    def tearDown(self): self.temp.cleanup()

    def mutate(self,fn):
        trace=self.output/'trace.json'
        events=read(trace)['events']
        fn(events)
        dump(trace,sign_events(events,self.hidden))
        return verify(self.public,self.hidden,self.output)

    def test_valid_reference(self):
        good,why=verify(self.public,self.hidden,self.output)
        self.assertTrue(good,why)

    def test_duplicate_custody_transfer(self):
        ok,reason=self.mutate(lambda ev: ev.insert(5,dict(ev[4])))
        self.assertFalse(ok,reason)
        self.assertIn('duplicate custody transfer',reason)

    def test_duplicate_request(self):
        ok,reason=self.mutate(lambda ev: ev.insert(2,dict(ev[1])))
        self.assertFalse(ok,reason)
        self.assertIn('duplicate consent request',reason)

    def test_false_user_notification(self):
        ok,reason=self.mutate(lambda ev: ev[7].update(message='KIT-B was never delivered; KIT-A was cancelled.'))
        self.assertFalse(ok,reason)
        self.assertIn('outbound notification',reason)

    def test_extra_side_effect_field(self):
        ok,reason=self.mutate(lambda ev: ev[6].update(revoke_original_kit_a=True))
        self.assertFalse(ok,reason)
        self.assertIn('event schema',reason)

    def test_duplicate_notification(self):
        def f(events):
            duplicate=dict(events[7]);duplicate['time']='2026-11-21T14:41:00+08:00'
            events.append(duplicate)
        ok,reason=self.mutate(f)
        self.assertFalse(ok,reason)
        self.assertIn('duplicate notification',reason)

    def test_missing_notification_proof(self):
        ok,reason=self.mutate(lambda ev: ev[7].pop('receipt_id'))
        self.assertFalse(ok,reason)
        self.assertIn('event schema',reason)

    def test_bad_notification_claim_reference(self):
        ok,reason=self.mutate(lambda ev: ev[7].update(receipt_id='RECEIPT-B-20261121'))
        self.assertFalse(ok,reason)
        self.assertIn('outbound notification',reason)

if __name__=='__main__':unittest.main()
