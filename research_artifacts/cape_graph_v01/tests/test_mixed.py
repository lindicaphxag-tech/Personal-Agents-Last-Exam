"""CAPE-Mix hidden-randomization, exact dual and independent LP regressions."""
from __future__ import annotations

import random
import unittest
from fractions import Fraction as F

from capegraph.adaptive import Probe, World
from capegraph.mixed import (solve_mixed, independent_replay, _mixture_optimum,
                             _exact_dual, exact_two_prior_game_reference)
from capegraph.planner import Goal, Need, Witness
from capegraph.robust import Prior, solve_robust


def witness(token, value='ok'):
    return Witness(token, value, 'official', 10)


def symmetric_case(p=F(1)):
    gs=(Goal('A', (Need('a','ok',('official',),0,100),),10),
        Goal('B', (Need('b','ok',('official',),0,100),),10))
    qs=(Probe('checkA',1,'official'), Probe('checkB',1,'official'))
    ws=(World('A',F(1,2), {'checkA':(witness('a'),), 'checkB':()}),
        World('B',F(1,2), {'checkA':(), 'checkB':(witness('b'),)}))
    ps=(Prior('A-prior',{'A':p,'B':1-p}),
        Prior('B-prior',{'A':1-p,'B':p}))
    return gs,qs,ws,ps


class MixedPolicyTests(unittest.TestCase):
    def test_mixing_strictly_beats_any_deterministic_tree(self):
        gs,qs,ws,ps=symmetric_case()
        deterministic=solve_robust(gs,qs,ws,1,ps)
        mixed=solve_mixed(gs,qs,ws,1,ps)
        self.assertEqual(deterministic.worst_case_reward,0)
        self.assertEqual(mixed.guaranteed_reward,5)
        self.assertEqual(mixed.dual_upper_bound,5)
        self.assertEqual(mixed.dual_prior_weights,(F(1,2),F(1,2)))
        self.assertEqual(sorted(x.probability for x in mixed.support),[F(1,2),F(1,2)])
        self.assertEqual({x.decision.query for x in mixed.support},{'checkA','checkB'})
        self.assertEqual(mixed.max_expected_cost,1)
        self.assertEqual(independent_replay(mixed,ws,qs,gs,ps),(F(5),F(1)))

    def test_random_seed_leakage_eliminates_randomized_guarantee(self):
        gs,qs,ws,ps=symmetric_case()
        mix=solve_mixed(gs,qs,ws,1,ps)
        # If nature sees the coin, it picks the defeating prior for each tree.
        leaked=sum((part.probability*min(part.scenario_rewards)
                    for part in mix.support), F(0))
        self.assertEqual(leaked,0)
        self.assertGreater(mix.guaranteed_reward,leaked)

    def test_coupled_mixture_preserves_one_prior_across_branches(self):
        gs,qs,ws,ps=symmetric_case(F(9,10))
        mixed=solve_mixed(gs,qs,ws,1,ps)
        self.assertEqual(mixed.guaranteed_reward,5)
        self.assertEqual(mixed.dual_upper_bound,5)
        self.assertEqual(independent_replay(mixed,ws,qs,gs,ps),(F(5),F(1)))
        self.assertEqual(solve_robust(gs,qs,ws,1,ps).worst_case_reward,1)

    def test_robust_common_proof_prefers_pure_policy(self):
        from experiments.robust_benchmark import designed
        gs,qs,ws,b,ps=designed('release')
        mix=solve_mixed(gs,qs,ws,b,ps)
        self.assertEqual(mix.guaranteed_reward,6)
        self.assertEqual(len(mix.support),1)
        self.assertEqual(mix.support[0].decision.query,'general')
        self.assertEqual(independent_replay(mix,ws,qs,gs,ps)[0],6)

    def test_zero_budget_stop_and_zero_cost(self):
        gs,qs,ws,ps=symmetric_case()
        mix=solve_mixed(gs,qs,ws,0,ps)
        self.assertEqual((mix.guaranteed_reward,mix.max_expected_cost),(0,0))
        self.assertEqual(mix.support[0].decision.query,None)
        self.assertEqual(independent_replay(mix,ws,qs,gs,ps),(0,0))

    def test_reject_more_or_fewer_than_two_priors(self):
        gs,qs,ws,ps=symmetric_case()
        with self.assertRaisesRegex(ValueError,'exactly 2 priors'):
            solve_mixed(gs,qs,ws,1,ps[:1])
        with self.assertRaisesRegex(ValueError,'exactly 2 priors'):
            solve_mixed(gs,qs,ws,1,ps+(Prior('third',{'A':F(1,2),'B':F(1,2)}),))

    def test_all_registered_scenarios_are_exactly_validated(self):
        from experiments.robust_benchmark import random_case
        for seed in range(60):
            with self.subTest(seed=seed):
                gs,qs,ws,b,ps=random_case(2026112400+seed)
                mix=solve_mixed(gs,qs,ws,b,ps)
                pure=solve_robust(gs,qs,ws,b,ps)
                self.assertGreaterEqual(mix.guaranteed_reward,pure.worst_case_reward)
                self.assertEqual(mix.guaranteed_reward,mix.dual_upper_bound)
                self.assertEqual(independent_replay(mix,ws,qs,gs,ps),
                                 (mix.guaranteed_reward,mix.max_expected_cost))
                self.assertLessEqual(len(mix.support),2)
                self.assertEqual(sum((s.probability for s in mix.support),F(0)),1)
                self.assertEqual(mix.as_dict(),solve_mixed(gs,qs,ws,b,ps).as_dict())

    def test_independent_scipy_lp_on_100_small_two_prior_games(self):
        # This independent LP is never used by the pure-Python runtime solver.
        rng=random.Random(20261124)
        for case in range(100):
            with self.subTest(case=case):
                n=rng.randint(2,8)
                reward=tuple((F(rng.randint(0,20),rng.choice((1,2,3,5))),
                              F(rng.randint(0,20),rng.choice((1,2,3,5))))
                             for _ in range(n))
                cost=tuple((F(rng.randint(0,4)), F(rng.randint(0,4)))
                           for _ in range(n))
                active, p, c=_mixture_optimum(reward,cost)
                val=min(p)
                d,upper=_exact_dual(reward,val)
                self.assertEqual(val,upper)
                self.assertLessEqual(len(active),2)
                self.assertEqual(sum(x[1] for x in active),1)
                self.assertAlmostEqual(float(val),exact_two_prior_game_reference(reward,cost),places=7)
                self.assertEqual(max(c),max(sum(weight*cost[i][k]
                                                  for i,weight in active)
                                                for k in (0,1)))
                self.assertEqual(max(sum(d[k]*reward[i][k] for k in (0,1))
                                     for i in range(n)),val)

    def test_exact_fraction_primal_dual_invariance_under_strategy_order(self):
        payoff=((F(10),F(0)),(F(0),F(10)),(F(3),F(3)))
        costs=((F(1),F(1)),(F(1),F(1)),(F(1),F(1)))
        v1=min(_mixture_optimum(payoff,costs)[1]);v2=min(_mixture_optimum(payoff[::-1],costs[::-1])[1]);
        self.assertEqual(v1,v2)
        self.assertEqual(v1,5)


if __name__=='__main__':
    unittest.main()
