from __future__ import annotations

import random
import unittest
from capegraph.planner import (Need, Goal, Query, Witness, solve_exact,
                               greedy_marginal, brute_force_oracle)


def n(t, val='yes', issuers=('service',), start=0, stop=100):
    return Need(t, val, issuers, start, stop)


def w(t, val='yes', issuer='service', at=50):
    return Witness(t, val, issuer, at)


def q(name, receipts, cost=1, channel='service'):
    return Query(name, cost, channel, tuple(receipts))


class PlannerTests(unittest.TestCase):
    def test_conjunction_beats_myopic_greedy(self):
        gs=[Goal('complete', (n('A'), n('B')), 10), Goal('decoy', (n('C'),), 4)]
        qs=[q('a',[w('A')],2),q('b',[w('B')],2),q('c',[w('C')],2)]
        p=solve_exact(gs,qs,4)
        self.assertEqual((p.selected,p.value,p.cost),(('a','b'),10,4))
        self.assertEqual((greedy_marginal(gs,qs,4).selected,greedy_marginal(gs,qs,4).value),(('c',),4))
        self.assertEqual((p.value,p.selected),(brute_force_oracle(gs,qs,4).value,brute_force_oracle(gs,qs,4).selected))

    def test_channel_mismatch_rejected_at_contract_boundary(self):
        with self.assertRaisesRegex(ValueError,'source channel'):
            q('fake',[w('token',issuer='other')])
        with self.assertRaisesRegex(ValueError,'read-only'):
            Query('danger',1,'service',(w('x'),),read_only=False)

    def test_wrong_issuer_and_expired_evidence_not_credited(self):
        g=[Goal('verified',(n('signed','valid',('hsm',),30,60),),7)]
        qs=[q('wrong',[w('signed','valid','service',40)],1),q('old',[w('signed','valid','hsm',20)],1,'hsm')]
        self.assertEqual(solve_exact(g,qs,2).value,0)
        qs.append(q('good',[w('signed','valid','hsm',50)],2,'hsm'))
        self.assertEqual(solve_exact(g,qs,2).selected,('good',))

    def test_conflicting_latest_authority_remains_unverified(self):
        g=[Goal('safe',(n('approval','yes'),),5)]
        initial=[w('approval','no',at=50)]
        qs=[q('old_good',[w('approval','yes',at=49)]),q('same_time_good',[w('approval','yes',at=50)])]
        self.assertEqual(solve_exact(g,qs,2,initial).value,0)
        qs.append(q('new_good',[w('approval','yes',at=60)],2))
        p=solve_exact(g,qs,2,initial)
        self.assertEqual((p.selected,p.value),(('new_good',),5))

    def test_empty_budget_never_fabricates_proof(self):
        g=[Goal('target',(n('token'),),10)]
        self.assertEqual((solve_exact(g,[q('read',[w('token')])],0).value),0)
        self.assertEqual((solve_exact(g,[],0,[w('token')]).value),10)

    def test_scopes_are_distinct_tokens(self):
        g=[Goal('A', (n('item:A/consent'),),5)]
        p=solve_exact(g,[q('Bconsent',[w('item:B/consent')])],1)
        self.assertEqual(p.value,0)

    def test_time_issuer_conflict_and_cost_tiebreak(self):
        g=[Goal('g',(n('a'),),5)]
        qs=[q('z',[w('a')],1),q('b',[w('a')],1),q('expensive',[w('a')],3)]
        p=solve_exact(g,qs,3)
        self.assertEqual((p.selected,p.cost),(('b',),1))

    def test_exact_matches_independent_enumeration_on_240_seeded_worlds(self):
        for seed in range(240):
            rng=random.Random(20261124+seed)
            tokens=[f'fact:{j}' for j in range(rng.randint(2,7))]
            goals=[]
            for i in range(rng.randint(2,5)):
                chosen=rng.sample(tokens,rng.randint(1,min(3,len(tokens))))
                goals.append(Goal(f'g{i}',tuple(n(t) for t in chosen),rng.randint(1,11)))
            qs=[]
            for j in range(rng.randint(3,9)):
                channel=rng.choice(['service','unknown'])
                receipts=tuple(w(t,rng.choice(['yes','yes','no']),channel,rng.randint(20,80))
                               for t in rng.sample(tokens,rng.randint(1,min(3,len(tokens)))))
                qs.append(q(f'q{j}',receipts,rng.randint(1,4),channel))
            budget=rng.randint(0,11)
            exact=solve_exact(goals,qs,budget)
            brute=brute_force_oracle(goals,qs,budget)
            self.assertEqual((exact.value,exact.cost,exact.selected),
                             (brute.value,brute.cost,brute.selected),f'seed {seed}')
            self.assertLessEqual(exact.explored_leaves,1<<len(qs))
            self.assertLessEqual(greedy_marginal(goals,qs,budget).value,exact.value)

    def test_permutation_invariance_with_symmetric_queries(self):
        gs=[Goal('proof',(n('A'),n('B')),7)]
        qs=[q('q-z',[w('A')],1),q('q-a',[w('A')],1),q('q-b',[w('B')],1)]
        a=solve_exact(gs,qs,2)
        b=solve_exact(list(reversed(gs)),list(reversed(qs)),2)
        self.assertEqual((a.value,a.selected),(b.value,b.selected))
        self.assertEqual(a.selected,('q-a','q-b'))

    def test_new_query_can_invalidate_older_positive_but_is_optional(self):
        gs=[Goal('verified',(n('authorization'),),9)]
        initial=(w('authorization','yes',at=25),)
        qs=[q('superseding_deny',[w('authorization','no',at=45)])]
        p=solve_exact(gs,qs,1,initial)
        self.assertEqual((p.selected,p.value),((),9))
        self.assertEqual(brute_force_oracle(gs,qs,1,initial).selected,())

    def test_more_budget_cannot_reduce_optimal_value(self):
        gs=[Goal('proof',(n('A'),n('B'),n('C')),11)]
        qs=[q('A',[w('A')]),q('B',[w('B')]),q('C',[w('C')])]
        scores=[solve_exact(gs,qs,b).value for b in range(5)]
        self.assertEqual(scores,[0,0,0,11,11])

    def test_limits_and_json_contract(self):
        with self.assertRaises(ValueError):
            solve_exact([], [q(f'x{i}',[w('a')]) for i in range(21)],8)
        with self.assertRaises(ValueError):
            Need('a',float('nan'),('svc',),0,20)
        with self.assertRaises(ValueError):
            Goal('dup',(n('a'),n('a')),1)
        with self.assertRaises(ValueError):
            Query('negative',-1,'svc',())
        p=solve_exact([Goal('g',(n('a'),),1)],[q('good',[w('a')])],1)
        self.assertEqual(len(p.as_dict()['sha256_without_digest']),64)


if __name__ == '__main__':
    unittest.main()
