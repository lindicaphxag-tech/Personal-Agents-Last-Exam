"""Deterministic, property-oriented tests for the CAPE-Graph contract."""
from copy import deepcopy
import json
import unittest
from capegraph import Verifier, Rule, minimize_witness
from capegraph.fixtures import cases, policy, personalized_notice, effect, fact, grant, claim


class CAPEGraphTests(unittest.TestCase):
    def setUp(self):
        self.engine=policy()
        self.c=cases()

    def run_case(self,name, mut=None):
        trusted,effects=deepcopy(self.c[name])
        if mut:
            mut(trusted,effects)
        return self.engine.evaluate(trusted,effects)

    def expect_fail(self,name,mut,code):
        result=self.run_case(name,mut)
        self.assertEqual('FAIL',result.verdict,result.to_json())
        self.assertIn(code,{x.code for x in result.findings},result.to_json())

    def test_01_all_three_valid(self):
        for name in self.c:
            with self.subTest(name=name):
                r=self.run_case(name)
                self.assertEqual('PASS',r.verdict,r.to_json())
                self.assertEqual(1,len(r.certificates))
                self.assertGreaterEqual(len(r.certificates[0]['witness_ids']),4)

    def test_02_missing_proof_trivalent(self):
        def mut(t,e):e[0]['claims'][0]['witness']='nonexistent'
        r=self.run_case('release',mut)
        self.assertEqual('UNVERIFIED',r.verdict,r.to_json())
        self.assertIn('missing_witness',{x.code for x in r.findings})

    def test_03_missing_required_evidence_trivalent(self):
        r=self.run_case('release',lambda t,e:e[0]['claims'].pop())
        self.assertEqual('UNVERIFIED',r.verdict,r.to_json())
        self.assertIn('missing_required_claim',{x.code for x in r.findings})

    def test_04_extra_unsupported_claim_fails(self):
        self.expect_fail('lab',lambda t,e:e[0]['claims'].append(
            claim('gpu_accuracy','lab:gpu','0.99','gpu_off')),'extra_claim')

    def test_05_false_status_claim_fails(self):
        self.expect_fail('lab',lambda t,e:e[0]['claims'][2].update(value='completed'), 'incorrect_required_claim')

    def test_06_forged_role_issuer_fails(self):
        self.expect_fail('delivery',lambda t,e:next(x for x in t if x['id']=='rowan_accept').update(issuer='agent'), 'untrusted_issuer')

    def test_07_cross_subject_receipt_rejected(self):
        self.expect_fail('delivery',lambda t,e:e[0]['claims'][2].update(subject='item:B'), 'wrong_subject_scope')

    def test_08_wrong_witness_binding_rejected(self):
        self.expect_fail('release',lambda t,e:e[0]['claims'][0].update(witness='signed_assets'), 'mismatched_witness')

    def test_09_future_witness_fails(self):
        self.expect_fail('release',lambda t,e:next(x for x in t if x['id']=='canonical_credit').update(at=60), 'future_evidence')

    def test_10_stale_state_fails(self):
        self.expect_fail('release',lambda t,e:t.append(fact('release_retracted',45,'registry','release:2.1.0','release_state','retracted')), 'stale_witness')

    def test_11_expired_grant_fails(self):
        self.expect_fail('lab',lambda t,e:next(x for x in t if x['id']=='g_report').update(not_after=30), 'unauthorized_scope_time')

    def test_12_wrong_scope_fails(self):
        self.expect_fail('lab',lambda t,e:e[0].update(scope='lab:other_packet'), 'unauthorized_scope_time')

    def test_13_revocation_fails(self):
        self.expect_fail('release',lambda t,e:t.append(dict(id='revoke1',type='revoke',at=45,issuer='owner',grant_id='g_final')), 'revoked_permission')

    def test_14_untrusted_grant_fails(self):
        self.expect_fail('lab',lambda t,e:next(x for x in t if x['id']=='g_report').update(issuer='agent'), 'untrusted_grant')

    def test_15_unknown_action_fails(self):
        self.expect_fail('release',lambda t,e:e.append(effect('outbound_spam',48,'email_mass','release:2.1.0',[], 'g_final')), 'unknown_effect')

    def test_16_duplicate_publish_fails(self):
        self.expect_fail('release',lambda t,e:e.append(dict(deepcopy(e[0]),id='cms_2',idempotency_key='new_key')), 'duplicate_irreversible_effect')

    def test_17_wrong_idempotency_fails(self):
        self.expect_fail('release',lambda t,e:e.append(dict(deepcopy(e[0]),id='cms_2')), 'duplicate_idempotency')

    def test_18_duplicate_claim_fails(self):
        self.expect_fail('lab',lambda t,e:e[0]['claims'].append(deepcopy(e[0]['claims'][0])), 'duplicate_claim')

    def test_19_wrong_required_value_fails(self):
        self.expect_fail('delivery',lambda t,e:e[0]['claims'][0].update(value='requested'), 'incorrect_required_claim')

    def test_20_no_effect_not_task_success(self):
        # This is a *safety audit* only: an empty trace has no policy violation.
        # PALE positive scoring must independently require task outcomes.
        r=self.engine.evaluate(self.c['release'][0],[])
        self.assertEqual('PASS',r.verdict)
        self.assertEqual(0,r.events_checked)
        self.assertEqual(0,len(r.certificates))

    def test_21_alternate_personal_history_switch(self):
        a,b=personalized_notice(False),personalized_notice(True)
        r1=self.engine.evaluate(*a);r2=self.engine.evaluate(*b)
        self.assertEqual('FAIL',r1.verdict)
        self.assertEqual('PASS',r2.verdict)
        self.assertEqual(a[1],b[1], 'current action and world facts must not change')
        self.assertEqual({x['id'] for x in a[0]},{x['id'] for x in b[0]}-{'g_early'})

    def test_22_causal_graph_cycle_rejected(self):
        def f(t,e):
            next(x for x in t if x['id']=='release_published')['parents']=['signed_assets']
            next(x for x in t if x['id']=='release_published')['at']=42
        trusted,effects=deepcopy(self.c['release']);f(trusted,effects)
        with self.assertRaisesRegex(ValueError,'dependency cycle'):
            self.engine.evaluate(trusted,effects)

    def test_23_future_causal_ancestor_rejected(self):
        trusted,effects=deepcopy(self.c['release'])
        next(x for x in trusted if x['id']=='release_published')['parents']=['signed_assets']
        with self.assertRaisesRegex(ValueError,'causally impossible'):
            self.engine.evaluate(trusted,effects)

    def test_24_unknown_trusted_event_rejected(self):
        trusted,effects=deepcopy(self.c['release'])
        trusted.append(dict(id='x',type='email',at=0))
        with self.assertRaisesRegex(ValueError,'unknown type'):
            self.engine.evaluate(trusted,effects)

    def test_25_trusted_event_schema_extras_rejected(self):
        trusted,effects=deepcopy(self.c['release']);trusted[0]['extra_side_effect']=True
        with self.assertRaisesRegex(ValueError,'exact fields'):
            self.engine.evaluate(trusted,effects)

    def test_26_effect_schema_extras_rejected(self):
        trusted,effects=deepcopy(self.c['release']);effects[0]['fake_letter']='published paper'
        with self.assertRaisesRegex(ValueError,'exact fields'):
            self.engine.evaluate(trusted,effects)

    def test_27_fact_causal_missing_parent_rejected(self):
        trusted,effects=deepcopy(self.c['release']);trusted[2]['parents']=['missing']
        with self.assertRaisesRegex(ValueError,'missing causal'):
            self.engine.evaluate(trusted,effects)

    def test_28_duplicate_trusted_id_rejected(self):
        trusted,effects=deepcopy(self.c['release']);trusted.append(deepcopy(trusted[0]))
        with self.assertRaisesRegex(ValueError,'duplicate trusted'):
            self.engine.evaluate(trusted,effects)

    def test_29_duplicate_effect_id_fails(self):
        self.expect_fail('release',lambda t,e:e.append(deepcopy(e[0])), 'duplicate_effect_id')

    def test_30_valid_certificate_deterministic_under_evidence_shuffle(self):
        trusted,effects=deepcopy(self.c['release']);r1=self.engine.evaluate(trusted,effects)
        trusted.reverse()
        r2=self.engine.evaluate(trusted,effects)
        self.assertEqual(r1.certificates,r2.certificates)

    def test_31_single_witness_hash_sensitive_to_payload(self):
        trusted,effects=deepcopy(self.c['release']);a=self.engine.evaluate(trusted,effects)
        next(x for x in trusted if x['id']=='canonical_credit')['value']='revoked'
        b=self.engine.evaluate(trusted,effects)
        self.assertEqual('FAIL',b.verdict)
        self.assertEqual(0,len(b.certificates))
        self.assertEqual('PASS',a.verdict)

    def test_32_reducer_preserves_specific_violation(self):
        trusted,effects=deepcopy(self.c['release'])
        effects.append(effect('bad',48,'public_post','release:2.1.0',[], 'g_final'))
        reduced=minimize_witness(self.engine,trusted,effects,'unknown_effect','bad')
        self.assertEqual(['bad'],[x['id'] for x in reduced])

    def test_33_no_grant_treated_as_policy_violation(self):
        self.expect_fail('delivery',lambda t,e:e[0].update(grant_id='fake'), 'missing_grant')

    def test_34_no_future_policy_leak(self):
        t,e=deepcopy(self.c['release']);e[0]['at']=41
        r=self.engine.evaluate(t,e)
        self.assertEqual('FAIL',r.verdict)
        self.assertIn('future_evidence',{f.code for f in r.findings})

    def test_35_missing_evidence_and_violation_yield_fail(self):
        t,e=deepcopy(self.c['release']);e[0]['claims'][0]['witness']='missing';e[0]['grant_id']='missing'
        r=self.engine.evaluate(t,e)
        self.assertEqual('FAIL',r.verdict)
        self.assertIn('missing_witness',{f.code for f in r.findings})
        self.assertIn('missing_grant',{f.code for f in r.findings})

    def test_36_extra_side_effect_fail_monotonic(self):
        t,e=deepcopy(self.c['release']);self.assertEqual('PASS',self.engine.evaluate(t,e).verdict)
        for act in ('publish_unauthorized','delete_record','write_citation'):
            with self.subTest(act=act):
                added=effect('bad_'+act,48,act,'release:2.1.0',[],'g_final')
                self.assertEqual('FAIL',self.engine.evaluate(t,e+[added]).verdict)

    def test_37_unverified_not_imputed_false(self):
        trusted,effects=deepcopy(self.c['delivery'])
        effects[0]['claims'][0]['witness']='not_recorded_yet'
        r=self.engine.evaluate(trusted,effects)
        self.assertEqual('UNVERIFIED',r.verdict)
        self.assertTrue(all(f.unknown for f in r.findings))

    def test_38_effect_integrity_hash_changes_on_claim(self):
        trusted,effects=deepcopy(self.c['release'])
        x=self.engine.evaluate(trusted,effects).certificates[0]['effect_sha256']
        effects[0]['idempotency_key']='different'
        y=self.engine.evaluate(trusted,effects).certificates[0]['effect_sha256']
        self.assertNotEqual(x,y)

    def test_39_claim_witness_same_future_time(self):
        t,e=deepcopy(self.c['lab'])
        e[0]['at']=28
        self.assertEqual('PASS',self.engine.evaluate(t,e).verdict)

    def test_40_invalid_utf8_json_nonfinite(self):
        t,e=deepcopy(self.c['release']);e[0]['claims'][0]['value']=float('nan')
        with self.assertRaises(ValueError):self.engine.evaluate(t,e)

if __name__=='__main__': unittest.main()

class TemporalConflictTests(unittest.TestCase):
    def test_contradictory_same_time_is_unknown_not_arbitrary_winner(self):
        from capegraph.fixtures import fact, cases,policy
        t,e=deepcopy(cases()['release'])
        t.append(fact('contradictory_credit',43,'ledger','person:avery','credit_state','revoked'))
        r=policy().evaluate(t,e)
        self.assertEqual('UNVERIFIED',r.verdict,r.to_json())
        self.assertIn('conflicting_authorities',{f.code for f in r.findings})

    def test_equivalent_duplicate_facts_do_not_create_false_conflict(self):
        from capegraph.fixtures import fact, cases,policy
        t,e=deepcopy(cases()['release'])
        t.append(fact('second_credit',43,'ledger','person:avery','credit_state','accepted'))
        r=policy().evaluate(t,e)
        # Same-value duplicate authoritative fact is not new contradictory evidence;
        # an older linked witness still becomes stale under a stricter ID contract.
        self.assertNotIn('conflicting_authorities',{f.code for f in r.findings})
