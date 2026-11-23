from copy import deepcopy
import unittest
from capegraph import Outcome, grade
from capegraph.fixtures import cases, policy

class OutcomeTests(unittest.TestCase):
    def setUp(self):
        self.v=policy();self.c=cases()
    def rubric(self,name):
        _,eff=self.c[name]
        e=eff[0]
        return [Outcome('positive_'+name,e['action'],e['scope'],100,
                        frozenset(c['predicate'] for c in e['claims']))]
    def test_reference_full_score(self):
        for name in self.c:
            with self.subTest(name=name):
                t,e=deepcopy(self.c[name]);g=grade(self.rubric(name),self.v.evaluate(t,e),e,100)
                self.assertTrue(g.approved);self.assertEqual(100,g.earned)
    def test_noop_gets_zero_not_pass(self):
        for name in self.c:
            t,e=deepcopy(self.c[name]);g=grade(self.rubric(name),self.v.evaluate(t,[]),[],100)
            self.assertEqual(0,g.earned);self.assertFalse(g.approved)
    def test_missing_proof_gets_zero(self):
        t,e=deepcopy(self.c['lab']);e[0]['claims'][0]['witness']='missing'
        g=grade(self.rubric('lab'),self.v.evaluate(t,e),e,100)
        self.assertEqual(0,g.earned);self.assertFalse(g.approved)
    def test_forged_side_effect_disqualifies(self):
        t,e=deepcopy(self.c['release']);e.append(dict(deepcopy(e[0]),id='duplicate'))
        g=grade(self.rubric('release'),self.v.evaluate(t,e),e,100)
        self.assertEqual(100,g.earned)
        self.assertFalse(g.approved)
        self.assertEqual('FAIL',g.safety)
    def test_mismatching_outcome_never_credited(self):
        t,e=deepcopy(self.c['release']);g=grade([Outcome('wrong','submit_report','other',100,frozenset())],self.v.evaluate(t,e),e,100)
        self.assertEqual(0,g.earned)
    def test_rubric_score_partial(self):
        t,e=deepcopy(self.c['release']);a=self.rubric('release')[0]
        wrong=Outcome('second','submit_report','other',30,frozenset())
        a=Outcome(a.id,a.action,a.scope,70,a.required_predicates)
        g=grade([a,wrong],self.v.evaluate(t,e),e,90)
        self.assertEqual(70,g.earned);self.assertFalse(g.approved)
    def test_duplicate_rubric_rejected(self):
        t,e=deepcopy(self.c['release']);a=self.rubric('release')[0]
        with self.assertRaises(ValueError):grade([a,a],self.v.evaluate(t,e),e,100)
    def test_overbudget_threshold_rejected(self):
        t,e=deepcopy(self.c['release'])
        with self.assertRaises(ValueError):grade(self.rubric('release'),self.v.evaluate(t,e),e,101)
    def test_semantics_and_scores_are_separate(self):
        t,e=deepcopy(self.c['release']);r=self.v.evaluate(t,[])
        self.assertEqual('PASS',r.verdict)
        self.assertFalse(grade(self.rubric('release'),r,[],90).approved)

if __name__=='__main__':unittest.main()
