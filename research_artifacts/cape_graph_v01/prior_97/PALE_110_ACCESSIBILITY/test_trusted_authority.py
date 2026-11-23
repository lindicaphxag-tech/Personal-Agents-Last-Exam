"""Adversarial consent/receipt attestations for PALE #110 offline pilot.

Run alongside the existing test_route_gate.py. This is author-side synthetic
falsification, not an official PALE run or proof of real volunteer consent.
"""
import unittest
import tempfile
from pathlib import Path
from route_gate import construct, reference, verify, read, dump, sign_events

class TrustedAuthorityRedTeam(unittest.TestCase):
    def setUp(self):
        self.work=tempfile.TemporaryDirectory()
        root=Path(self.work.name)
        self.public=root/'public'
        self.hidden=root/'hidden'
        self.output=root/'output'
        construct(self.public,self.hidden)
        reference(self.public,self.hidden,self.output)

    def tearDown(self):
        self.work.cleanup()

    def signed_mutation(self,mutate):
        p=self.output/'trace.json'
        events=read(p)['events']
        mutate(events)
        dump(p,sign_events(events,self.hidden))
        return verify(self.public,self.hidden,self.output)

    def test_canonical_reference_still_passes(self):
        ok,why=verify(self.public,self.hidden,self.output)
        self.assertTrue(ok,why)

    def test_well_formed_fake_receipt_id_rejected(self):
        ok,why=self.signed_mutation(
            lambda ev: ev[6].update(receipt_id='RECEIPT-C-FORGED-PREFIX'))
        self.assertFalse(ok,why)
        self.assertIn('unattested delivery receipt',why)

    def test_early_self_asserted_consent_rejected(self):
        ok,why=self.signed_mutation(
            lambda ev: ev[3].update(time='2026-11-21T14:01:00+08:00'))
        self.assertFalse(ok,why)
        self.assertIn('unattested volunteer consent',why)

    def test_other_credential_cannot_authorize_consent(self):
        ok,why=self.signed_mutation(
            lambda ev: ev[3].update(consent_id='CONSENT-OTHER-ITEM'))
        self.assertFalse(ok,why)
        self.assertIn('unattested volunteer consent',why)

    def test_duplicate_acceptance_event_rejected(self):
        def mutation(ev):
            ev.insert(4,dict(ev[3]))
        ok,why=self.signed_mutation(mutation)
        self.assertFalse(ok,why)
        self.assertIn('duplicate consent',why)

    def test_kib_fake_well_formed_receipt_rejected(self):
        ok,why=self.signed_mutation(
            lambda ev: ev[2].update(receipt_id='RECEIPT-B-FORGED-PREFIX'))
        self.assertFalse(ok,why)
        self.assertIn('unattested delivery receipt',why)

    def test_canonical_receipt_cannot_be_backdated(self):
        ok,why=self.signed_mutation(
            lambda ev: ev[6].update(time='2026-11-21T14:31:00+08:00'))
        self.assertFalse(ok,why)

if __name__ == '__main__':
    unittest.main()
