"""Independent exact min-over-fixed-priors and trust boundary regression tests."""
from __future__ import annotations

from fractions import Fraction as F
import random
import unittest

from capegraph.adaptive import Probe, World, solve_adaptive
from capegraph.planner import Goal, Need, Witness, _grade
from capegraph.robust import (Prior, solve_robust, exhaustive_independent_reference,
                              robust_fixed_reference, replay_robust)


def witness(t, value='ok'):
    return Witness(t, value, 'official', 10)


def fixed_case():
    gs = (Goal('specific', (Need('A', 'ok', ('official',), 1, 100),), 10),
          Goal('common', (Need('G', 'ok', ('official',), 1, 100),), 6))
    qs = (Probe('askA', 1, 'official'), Probe('askG', 1, 'official'))
    ws = (World('A', F(1, 2), {'askA': (witness('A'),), 'askG': (witness('G'),)}),
          World('B', F(1, 2), {'askA': (), 'askG': (witness('G'),)}))
    scenarios = (Prior('nominal', {'A': F(9, 10), 'B': F(1, 10)}),
                 Prior('shifted', {'A': F(1, 10), 'B': F(9, 10)}))
    return gs, qs, ws, scenarios


def random_problem(seed):
    rng = random.Random(seed)
    toks = [f'x{i}' for i in range(rng.randrange(2, 5))]
    gs = tuple(Goal(f'g{i}', tuple(Need(x, 'ok', ('official',), 1, 100)
                                    for x in rng.sample(toks, rng.randrange(1, len(toks) + 1))),
                    rng.randint(2, 11)) for i in range(rng.randint(1, 4)))
    qs = tuple(Probe(f'q{i}', rng.randint(1, 2), 'official')
               for i in range(rng.randint(2, 4)))
    n = rng.randint(2, 3)
    ws = []
    for i in range(n):
        responses = {}
        for q in qs:
            subset = rng.sample(toks, rng.randint(0, min(2, len(toks))))
            responses[q.name] = tuple(witness(t, rng.choice(['ok','ok','bad'])) for t in subset)
        ws.append(World(f'w{i}', F(1, n), responses))
    scenarios = []
    for j in range(rng.randint(1, 3)):
        weights = [rng.randrange(0, 8) for _ in range(n)]
        if not any(weights):
            weights[0] = 1
        t = sum(weights)
        scenarios.append(Prior(f'p{j}', {f'w{i}': F(a, t) for i, a in enumerate(weights)}))
    return gs, qs, tuple(ws), tuple(scenarios), rng.randint(0, 4)


class RobustPlanningTest(unittest.TestCase):
    def test_prior_shift_changes_optimal_policy(self):
        gs, qs, ws, ps = fixed_case()
        nominal = solve_robust(gs, qs, ws, 1, ps[:1])
        robust = solve_robust(gs, qs, ws, 1, ps)
        self.assertEqual(nominal.decision.query, 'askA')
        self.assertEqual(robust.decision.query, 'askG')
        self.assertEqual(nominal.worst_case_reward, 9)
        self.assertEqual(robust.worst_case_reward, 6)
        self.assertEqual(tuple(replay_robust(robust, w, qs, gs)[0] for w in ws), (6, 6))
        self.assertEqual(robust_fixed_reference(gs, qs, ws, 1, ps), (6, ('askG',)))

    def test_strict_improvement_in_shifted_worst_case(self):
        gs, qs, ws, ps = fixed_case()
        nominal = solve_robust(gs, qs, ws, 1, ps[:1])
        robust = solve_robust(gs, qs, ws, 1, ps)
        actual_nominal_worst = min(
            sum(p.probabilities[w.name] * replay_robust(nominal, w, qs, gs)[0]
                for w in ws) for p in ps)
        self.assertEqual(actual_nominal_worst, 1)
        self.assertEqual(robust.worst_case_reward, 6)
        self.assertEqual(robust.worst_case_reward - actual_nominal_worst, 5)

    def test_a_single_prior_recovers_v03_bayesian_optimality(self):
        gs, qs, ws, ps = fixed_case()
        nominal_worlds = tuple(World(w.name, ps[0].probabilities[w.name], w.responses) for w in ws)
        r = solve_robust(gs, qs, nominal_worlds, 1, ps[:1])
        v03 = solve_adaptive(gs, qs, nominal_worlds, 1)
        self.assertEqual(r.worst_case_reward, v03.decision.expected_goal_value)
        self.assertEqual(r.worst_case_cost, v03.decision.expected_query_cost)

    def test_coupled_prior_is_fixed_across_observation_branches(self):
        """Naive branchwise switching of ambiguous priors is invalid."""
        gs=(Goal('A',(Need('proofA','ok',('official',),0,100),),10),
            Goal('B',(Need('proofB','ok',('official',),0,100),),10))
        qs=(Probe('which',1,'official'),Probe('checkA',2,'official'),Probe('checkB',2,'official'))
        def rec(name,branch,good):
            return World(name,F(1,4),{
                'which':(Witness('branch',branch,'official',10),),
                'checkA':(witness('proofA'),) if branch=='A' and good else (),
                'checkB':(witness('proofB'),) if branch=='B' and good else ()})
        ws=(rec('AG','A',True),rec('AB','A',False),
            rec('BG','B',True),rec('BB','B',False))
        ps=(Prior('p1',{'AG':F(2,5),'AB':F(1,10),'BG':F(1,20),'BB':F(9,20)}),
            Prior('p2',{'AG':F(1,20),'AB':F(9,20),'BG':F(2,5),'BB':F(1,10)}))
        r=solve_robust(gs,qs,ws,3,ps)
        self.assertEqual(r.decision.query,'which')
        self.assertEqual(r.worst_case_reward,F(9,2))
        self.assertEqual(robust_fixed_reference(gs,qs,ws,3,ps)[0],F(1,2))
        self.assertEqual(exhaustive_independent_reference(gs,qs,ws,3,ps),
                         (r.worst_case_reward,r.worst_case_cost))
        stagewise_switching_undercount=10*(ps[1].probabilities['AG']+
                                           ps[0].probabilities['BG'])
        self.assertEqual(stagewise_switching_undercount,1)
        self.assertGreater(r.worst_case_reward,stagewise_switching_undercount)

    def test_zero_query_budget_stop_always_exists(self):
        gs, qs, ws, ps = fixed_case()
        r = solve_robust(gs, qs, ws, 0, ps)
        self.assertIsNone(r.decision.query)
        self.assertEqual((r.worst_case_reward, r.worst_case_cost), (0, 0))

    def test_missing_prior_world_rejected(self):
        gs, qs, ws, _ = fixed_case()
        with self.assertRaisesRegex(ValueError, 'assign every world'):
            solve_robust(gs, qs, ws, 1, (Prior('x', {'A': F(1)}),))

    def test_unnormalized_prior_rejected(self):
        gs, qs, ws, _ = fixed_case()
        with self.assertRaisesRegex(ValueError, 'sum exactly'):
            solve_robust(gs, qs, ws, 1, (Prior('x', {'A': F(1, 2), 'B': F(1, 4)}),))

    def test_negative_prior_rejected(self):
        gs, qs, ws, _ = fixed_case()
        with self.assertRaisesRegex(ValueError, 'nonnegative'):
            solve_robust(gs, qs, ws, 1, (Prior('x', {'A': F(2), 'B': F(-1)}),))

    def test_duplicate_prior_label_rejected(self):
        gs, qs, ws, ps = fixed_case()
        with self.assertRaisesRegex(ValueError, 'distinct'):
            solve_robust(gs, qs, ws, 1, (ps[0], ps[0]))

    def test_wrong_issuer_rejected_before_policy(self):
        gs, qs, ws, ps = fixed_case()
        bad = (World('A', F(1, 2), {'askA': (Witness('A','ok','fake',10),), 'askG': ()}),ws[1])
        with self.assertRaisesRegex(ValueError, 'correct service-bound'):
            solve_robust(gs, qs, bad, 1, ps)

    def test_read_only_query_required(self):
        with self.assertRaisesRegex(ValueError, 'read only'):
            Probe('mutation', 1, 'official', read_only=False)

    def test_independent_oracle_exhaustive_random(self):
        for seed in range(112):
            with self.subTest(seed=seed):
                gs, qs, ws, ps, budget = random_problem(seed + 2026112400)
                robust = solve_robust(gs, qs, ws, budget, ps)
                separate = exhaustive_independent_reference(gs, qs, ws, budget, ps)
                self.assertEqual((robust.worst_case_reward, robust.worst_case_cost), separate)
                self.assertGreaterEqual(robust.worst_case_reward,
                                        robust_fixed_reference(gs, qs, ws, budget, ps)[0])
                for w in ws:
                    reward,cost = replay_robust(robust, w, qs, gs)
                    self.assertLessEqual(cost,budget)
                    self.assertEqual(reward, dict(robust.per_world_rewards)[w.name])
                    self.assertEqual(cost, dict(robust.per_world_costs)[w.name])

    def test_canonical_model_order_irrelevant(self):
        gs, qs, ws, ps = fixed_case()
        a = solve_robust(gs, qs, ws, 1, ps)
        b = solve_robust(reversed(gs), reversed(qs), reversed(ws), 1, reversed(ps))
        self.assertEqual(a.as_dict(), b.as_dict())

    def test_nonfinite_expected_value_rejected(self):
        with self.assertRaises(ValueError):
            Goal('bad', (Need('x', float('nan'), ('official',), 0, 100),), 1)

    def test_conflicting_equal_time_receipts_not_rewarded(self):
        gs=(Goal('g',(Need('x','ok',('official',),1,100),),9),)
        self.assertEqual(_grade(gs, (witness('x'), witness('x','bad')))[0], 0)
        qs=(Probe('good',1,'official'),Probe('bad',1,'official'))
        ws=(World('w',F(1),{'good':(witness('x'),), 'bad':(witness('x','bad'),)}),)
        ps=(Prior('p',{'w':F(1)}),)
        r=solve_robust(gs,qs,ws,2,ps)
        self.assertEqual(r.worst_case_reward,9)
        self.assertEqual(r.decision.query,'good')
        self.assertEqual(replay_robust(r,ws[0],qs,gs),(9,1))


if __name__=='__main__':
    unittest.main()
