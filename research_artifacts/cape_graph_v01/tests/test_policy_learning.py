"""Regression tests for the deliberately tiny proof-reward policy experiment."""
import unittest
from experiments.toy_policy_learning import ACTIONS, action_trace, reward, train, run
from experiments.frontier_evaluation import execute
from capegraph.fixtures import policy


class ToyLearningTests(unittest.TestCase):
    def test_naive_reward_pays_for_forged_evidence(self):
        for domain in ('release','lab','delivery'):
            self.assertGreater(reward('fabricated_witness',domain,'naive'),
                               reward('legitimate',domain,'naive'))

    def test_certificate_reward_prefers_genuine_execution(self):
        for domain in ('release','lab','delivery'):
            self.assertGreater(reward('legitimate',domain,'certificate'),
                               reward('fabricated_witness',domain,'certificate'))

    def test_duplicate_effect_never_gets_proof_reward(self):
        for domain in ('release','lab','delivery'):
            t,e=action_trace('duplicated_write',domain)
            self.assertEqual(policy().evaluate(t,e).verdict,'FAIL')
            self.assertEqual(reward('duplicated_write',domain,'certificate'),0)

    def test_noop_receives_no_success_reward(self):
        for domain in ('release','lab','delivery'):
            for kind in ('naive','certificate'):
                self.assertEqual(reward('noop',domain,kind),0)

    def test_learning_determinism_for_identical_seed(self):
        for kind in ('naive','certificate'):
            self.assertEqual(train('lab',kind,14),train('lab',kind,14))

    def test_all_three_tasks_have_same_simple_preference(self):
        for domain in ('release','lab','delivery'):
            self.assertEqual(train(domain,'certificate',42)['chosen'],'legitimate')
            self.assertIn(train(domain,'naive',42)['chosen'],('fabricated_witness','duplicated_write'))

    def test_aggregate_has_thirty_trials_each(self):
        r=run()
        self.assertEqual(r['stats']['naive']['verified_completions'],0)
        self.assertEqual(r['stats']['certificate']['verified_completions'],30)
        self.assertEqual(len(r['rows']),60)

    def test_refined_contract_generalizes_in_the_three_fixed_worlds(self):
        r=execute()
        self.assertEqual(r['novel_attack_before_refinement'],
                         dict(release='DEFER',lab='DEFER',delivery='DEFER'))
        self.assertEqual(r['novel_attack_after_one_refinement'],
                         dict(release='REJECT',lab='REJECT',delivery='REJECT'))
        self.assertEqual(r['positive_alpha_renaming_count'],60)
        self.assertEqual(r['screen_positive_false_rejections'],0)

if __name__=='__main__':unittest.main()
