"""Finite-example CECS checks; not a formal policy soundness proof."""
from copy import deepcopy
import unittest
from capegraph.cecs import Screen, GUARDS, synthesize
from capegraph.fixtures import cases, policy, personalized_notice
from experiments.ablation import MODES, mutate


class CounterexampleSynthesisTests(unittest.TestCase):
    def setUp(self):
        self.engine=policy()
        self.cases=cases()
        self.good=[deepcopy(x) for x in self.cases.values()]
        self.bad=[]
        for key in self.cases:
            for mode in MODES:
                t,e=deepcopy(self.cases[key]);mutate(t,e,mode)
                self.bad.append((t,e))

    def test_all_reference_traces_pass_oracle(self):
        for t,e in self.good:
            self.assertEqual(self.engine.evaluate(t,e).verdict,'PASS')

    def test_all_mutants_oracle_nonpassing(self):
        self.assertEqual(len(self.bad),42)
        for t,e in self.bad:
            self.assertNotEqual(self.engine.evaluate(t,e).verdict,'PASS')

    def test_guards_have_stable_names_and_positive_safe(self):
        self.assertEqual(len({x.name for x in GUARDS}),len(GUARDS))
        for g in GUARDS:
            for t,e in self.good:
                self.assertFalse(g.detects(t,e,self.engine),(g.name,t,e))

    def test_cecs_converges_and_explains_selection(self):
        plan=synthesize(self.engine,self.good,self.bad)
        self.assertGreater(len(plan.selected),0)
        self.assertEqual(len(plan.rounds),len(plan.selected))
        self.assertGreater(plan.train_negative_covered,25)
        self.assertLessEqual(plan.train_negative_covered,42)
        self.assertEqual(plan.certified_positives,3)
        self.assertEqual(plan.cost,sum(g.cost for g in GUARDS if g.name in plan.selected))

    def test_no_success_authorized_by_cheap_screen(self):
        plan=synthesize(self.engine,self.good,self.bad)
        screen=Screen(self.engine,plan.selected)
        for t,e in self.good+self.bad:
            decision,_=screen.check(t,e)
            self.assertIn(decision,('REJECT','DEFER'))

    def test_deferred_always_rechecked_with_full_oracle(self):
        plan=synthesize(self.engine,self.good,self.bad)
        screen=Screen(self.engine,plan.selected)
        for t,e in self.good+self.bad:
            (_, _), truth=screen.verified(t,e)
            self.assertEqual(truth.verdict,self.engine.evaluate(t,e).verdict)

    def test_leave_one_domain_out_sanity(self):
        for held in self.cases:
            positives=[deepcopy(v) for k,v in self.cases.items() if k!=held]
            negatives=[]
            for k,x in self.cases.items():
                if k==held:continue
                for m in MODES:
                    t,e=deepcopy(x);mutate(t,e,m);negatives.append((t,e))
            plan=synthesize(self.engine,positives,negatives)
            screen=Screen(self.engine,plan.selected)
            valid=deepcopy(self.cases[held]);self.assertEqual(screen.check(*valid)[0],'DEFER')
            held_bad=[]
            for m in MODES:
                t,e=deepcopy(self.cases[held]);mutate(t,e,m);held_bad.append((t,e))
            # Any missed out-of-domain mutation is deferred, not accepted.
            self.assertTrue(all(screen.check(*x)[0] in ('DEFER','REJECT') for x in held_bad))

    def test_bad_input_does_not_turn_into_pass(self):
        t,e=deepcopy(self.cases['lab'])
        e[0]['claims'].append({'unknown':'field'})
        decision,_=Screen(self.engine,('schema',)).check(t,e)
        self.assertEqual(decision,'REJECT')

    def test_invalid_training_labels_cannot_leak(self):
        with self.assertRaisesRegex(ValueError,'positive examples'):
            synthesize(self.engine,[self.bad[0]],self.bad[1:])
        with self.assertRaisesRegex(ValueError,'negative examples'):
            synthesize(self.engine,self.good,[self.good[0]])

    def test_unknown_guard_name_is_error(self):
        with self.assertRaises(ValueError):Screen(self.engine,['paper_author_fabricator'])

    def test_context_only_change_affects_authority(self):
        forbidden,permitted=personalized_notice(False),personalized_notice(True)
        self.assertEqual(forbidden[1],permitted[1])
        a=Screen(self.engine,('authorization',))
        self.assertEqual(a.check(*forbidden)[0],'REJECT')
        self.assertEqual(a.check(*permitted)[0],'DEFER')

if __name__=='__main__':unittest.main()

class RelationalProofBindingTests(unittest.TestCase):
    def setUp(self):self.engine=policy()

    def test_unrelated_but_issuer_valid_delivery_proof_must_fail(self):
        t,e=deepcopy(cases()['delivery'])
        next(x for x in t if x['id']=='receipt_C')['parents']=[]
        result=self.engine.evaluate(t,e)
        self.assertEqual(result.verdict,'FAIL')
        self.assertIn('unbound_cross_service_proof',{x.code for x in result.findings})

    def test_delivery_receipt_must_depend_on_both_consent_and_route(self):
        t,e=deepcopy(cases()['delivery'])
        next(x for x in t if x['id']=='receipt_C')['parents']=['rowan_accept']
        self.assertEqual(self.engine.evaluate(t,e).verdict,'FAIL')

    def test_cpu_receipt_requires_protocol_ancestry(self):
        t,e=deepcopy(cases()['lab'])
        next(x for x in t if x['id']=='cpu_receipt')['parents']=[]
        self.assertEqual(self.engine.evaluate(t,e).verdict,'FAIL')

    def test_release_signature_requires_published_registry_link(self):
        t,e=deepcopy(cases()['release'])
        next(x for x in t if x['id']=='signed_assets')['parents']=[]
        self.assertEqual(self.engine.evaluate(t,e).verdict,'FAIL')

    def test_independent_witness_order_not_a_substitute_for_dependency(self):
        t,e=deepcopy(cases()['delivery'])
        next(x for x in t if x['id']=='receipt_C')['parents']=[]
        t.reverse()
        self.assertEqual(self.engine.evaluate(t,e).verdict,'FAIL')

    def test_fast_relational_screen_flags_detached_proof(self):
        t,e=deepcopy(cases()['delivery'])
        next(x for x in t if x['id']=='receipt_C')['parents']=[]
        self.assertEqual(Screen(self.engine,['relational']).check(t,e)[0],'REJECT')

    def test_fresh_reference_still_passes_relational_check(self):
        for t,e in cases().values():
            self.assertEqual(self.engine.evaluate(t,e).verdict,'PASS')
            self.assertEqual(Screen(self.engine,['relational']).check(t,e)[0],'DEFER')

class MetamorphicAndNovelFamilies(unittest.TestCase):
    def setUp(self):self.engine=policy()

    def test_alpha_renaming_preserves_three_reference_verdicts(self):
        from capegraph.metamorphic import rename_world
        for name,(t,e) in cases().items():
            for seed in range(10):
                a,b=rename_world(t,e,seed)
                self.assertEqual(self.engine.evaluate(a,b).verdict,'PASS',(name,seed))

    def test_detached_authoritative_receipt_is_a_novel_fail(self):
        for name,(t,e) in cases().items():
            a,b=deepcopy((t,e))
            proof_id={'release':'signed_assets','lab':'cpu_receipt','delivery':'receipt_C'}[name]
            next(z for z in a if z['id']==proof_id)['parents']=[]
            out=self.engine.evaluate(a,b)
            self.assertEqual(out.verdict,'FAIL')
            self.assertIn('unbound_cross_service_proof',{x.code for x in out.findings})

    def test_counterexample_guided_refinement_adds_relational_guard(self):
        engine=self.engine;worlds=cases()
        positives=[deepcopy(v) for v in worlds.values()]
        negatives=[]
        for name,world in worlds.items():
            for mode in MODES:
                t,e=deepcopy(world);mutate(t,e,mode);negatives.append((t,e))
        original=synthesize(engine,positives,negatives)
        self.assertNotIn('relational',original.selected)
        t,e=deepcopy(worlds['lab'])
        next(x for x in t if x['id']=='cpu_receipt')['parents']=[]
        self.assertEqual(Screen(engine,original.selected).check(t,e)[0],'DEFER')
        updated=synthesize(engine,positives,negatives+[(t,e)])
        self.assertIn('relational',updated.selected)
        for name,(tr,ef) in worlds.items():
            tt,ee=deepcopy((tr,ef))
            proof={'release':'signed_assets','lab':'cpu_receipt','delivery':'receipt_C'}[name]
            next(x for x in tt if x['id']==proof)['parents']=[]
            self.assertEqual(Screen(engine,updated.selected).check(tt,ee)[0],'REJECT')

    def test_new_guard_preserves_all_alpha_renamed_positives(self):
        from capegraph.metamorphic import rename_world
        guard=Screen(self.engine,('relational',))
        for t,e in cases().values():
            for seed in range(10,20):
                aa,bb=rename_world(t,e,seed)
                self.assertEqual(guard.check(aa,bb)[0],'DEFER')
