from copy import deepcopy
from dataclasses import replace
import unittest
from capegraph.core import digest
from capegraph.fixtures import cases, policy, effect
from capegraph.scoring import Outcome
from capegraph.proof_reward import replay_reward, verify_reward_trace, reward_for_training


RUBRICS={
 'release':(Outcome('release','publish_release','release:2.1.0',100,frozenset({'release_state','signature_state','credit_state'})),),
 'lab':(Outcome('report','submit_report','lab:packet',100,frozenset({'cpu_status','holdout','gpu_status'})),),
 'delivery':(Outcome('item','deliver_item','item:C',100,frozenset({'consent','route','delivery'})),),
}


class ProofCarryingRewardTests(unittest.TestCase):
    def setUp(self):self.engine=policy();self.worlds=cases()

    def test_all_three_positive_reference_reward(self):
        for name,(t,e) in self.worlds.items():
            with self.subTest(name=name):
                r=replay_reward(self.engine,RUBRICS[name],t,e,90,name)
                self.assertEqual(r.final_reward,1.0)
                self.assertEqual([x.credited for x in r.records],[0.0,1.0])
                self.assertEqual([x.delta for x in r.records],[0.0,1.0])
                self.assertTrue(verify_reward_trace(r,self.engine,RUBRICS[name],t,e,90))
                self.assertEqual(r.records[1].certified_effects,(e[0]['id'],))

    def test_noop_reward_is_zero(self):
        t,e=self.worlds['release'];r=replay_reward(self.engine,RUBRICS['release'],t,[],90)
        self.assertEqual(r.final_reward,0.0)
        self.assertEqual(r.records[0].verdict,'PASS')

    def test_unknown_proof_cannot_earn_positive(self):
        t,e=deepcopy(self.worlds['release']);e[0]['claims'][0]['witness']='unknown'
        r=replay_reward(self.engine,RUBRICS['release'],t,e,90)
        self.assertEqual(r.records[-1].verdict,'UNVERIFIED')
        self.assertEqual(r.final_reward,0.0)

    def test_attack_rolls_back_provisional_reward(self):
        t,e=deepcopy(self.worlds['release'])
        e.append(effect('spurious',60,'undeclared_post','release:2.1.0',[],e[0]['grant_id']))
        r=replay_reward(self.engine,RUBRICS['release'],t,e,90)
        self.assertEqual([x.credited for x in r.records],[0.0,1.0,0.0])
        self.assertEqual([x.delta for x in r.records],[0.0,1.0,-1.0])
        self.assertEqual(r.records[-1].verdict,'FAIL')
        self.assertEqual(reward_for_training(r.records[-1]),-1.0)

    def test_duplicate_effect_also_rolls_back(self):
        t,e=deepcopy(self.worlds['lab']);e.append(dict(e[0],id='duplicate'))
        r=replay_reward(self.engine,RUBRICS['lab'],t,e,90)
        self.assertEqual(r.final_reward,0.0)
        self.assertEqual(r.records[-1].delta,-1.0)

    def test_forged_certificate_rejected_on_replay(self):
        t,e=deepcopy(self.worlds['delivery'])
        r=replay_reward(self.engine,RUBRICS['delivery'],t,e,90)
        forged=replace(r,trace_digest='0'*64)
        self.assertFalse(verify_reward_trace(forged,self.engine,RUBRICS['delivery'],t,e,90))
        forged_record=replace(r.records[-1],proof_digest='0'*64)
        self.assertFalse(verify_reward_trace(replace(r,records=r.records[:-1]+(forged_record,)),self.engine,RUBRICS['delivery'],t,e,90))

    def test_outcome_tamper_detected_by_replay(self):
        t,e=deepcopy(self.worlds['release'])
        r=replay_reward(self.engine,RUBRICS['release'],t,e,90)
        e[0]['claims'][0]['value']='fabricated'
        self.assertFalse(verify_reward_trace(r,self.engine,RUBRICS['release'],t,e,90))

    def test_policy_mutation_detected_by_replay(self):
        t,e=deepcopy(self.worlds['release'])
        r=replay_reward(self.engine,RUBRICS['release'],t,e,90)
        changed=(Outcome('release','publish_release','release:2.1.0',100,frozenset({'release_state'})),)
        self.assertFalse(verify_reward_trace(r,self.engine,changed,t,e,90))

    def test_deterministic_under_trusted_record_order(self):
        t,e=deepcopy(self.worlds['lab'])
        one=replay_reward(self.engine,RUBRICS['lab'],t,e,90)
        t.reverse()
        two=replay_reward(self.engine,RUBRICS['lab'],t,e,90)
        self.assertEqual(one.records[-1].proof_digest,two.records[-1].proof_digest)
        # Raw independent evidence stream hash intentionally detects different input order.
        self.assertNotEqual(one.records[-1].evidence_digest,two.records[-1].evidence_digest)

    def test_invalid_threshold_rejected(self):
        t,e=self.worlds['lab']
        with self.assertRaises(ValueError):replay_reward(self.engine,RUBRICS['lab'],t,e,101)

    def test_invalid_run_identity_rejected(self):
        t,e=self.worlds['lab']
        with self.assertRaises(ValueError):replay_reward(self.engine,RUBRICS['lab'],t,e,90,run_id='')

if __name__=='__main__':unittest.main()
