from copy import deepcopy
import unittest
from capegraph.ingest import ingest_service_streams
from capegraph.fixtures import cases,policy

class TrustedIngest(unittest.TestCase):
    def setUp(self):
        self.t,self.e=deepcopy(cases()['release'])
        self.channels={}
        for x in self.t:
            issuer=x.pop('issuer')
            self.channels.setdefault(issuer,[]).append(x)
        self.effect_channels={'cms':[self.e[0]]}
        self.authorized=set(self.channels)

    def call(self,**updates):
        args=dict(trusted_channels=self.channels,effect_channels=self.effect_channels,
                  allowed_fact_channels=self.authorized,allowed_effect_channels={'cms'})
        args.update(updates)
        return ingest_service_streams(**args)

    def test_complete_ingest_preserves_validated_replay(self):
        trusted,effects=self.call()
        self.assertEqual('PASS',policy().evaluate(trusted,effects).verdict)
    def test_attacker_cannot_assert_issuer_in_claimed_record(self):
        self.channels['registry'][0]['issuer']='registry'
        with self.assertRaisesRegex(ValueError,'issuer cannot be asserted'):
            self.call()
    def test_unknown_provenance_channel_rejected(self):
        self.channels['agent']=[dict(self.channels['registry'][0])]
        with self.assertRaisesRegex(ValueError,'unapproved trusted'):
            self.call()
    def test_unknown_side_effect_channel_rejected(self):
        self.effect_channels['agent_transcript']=[dict(self.e[0])]
        with self.assertRaisesRegex(ValueError,'unapproved committed'):
            self.call()
    def test_agent_side_claim_not_committed_effect(self):
        t,e=self.call(effect_channels={})
        r=policy().evaluate(t,e)
        self.assertEqual(0,r.events_checked)
        # The caller must grade positive task completion separately.
    def test_source_spoofed_extra_fields_rejected(self):
        self.channels['registry'][0]['forged_credit']='academic_coauthor'
        with self.assertRaisesRegex(ValueError,'expected exact fields'):
            self.call()

if __name__=='__main__': unittest.main()
