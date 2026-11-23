from __future__ import annotations

from fractions import Fraction as F
import random
import unittest

from capegraph.adaptive import (Probe, World, solve_adaptive, evaluate_fixed,
                                 expected_replay, execute_policy, response_id)
from capegraph.planner import Goal, Need, Witness


def need(token,issuer='svc',expected='yes'):
    return Need(token,expected,(issuer,),0,100)


def world(name,numer,denominator,responses):
    return World(name,F(numer,denominator),responses)


def obs(token,issuer='svc',value='yes',at=30):
    return Witness(token,value,issuer,at)


class AdaptiveTests(unittest.TestCase):
    def test_hidden_world_observation_enables_true_adaptivity_gain(self):
        goals=[Goal('A',(need('a'),need('a2')),10),Goal('B',(need('b'),need('b2')),10)]
        probes=[Probe('read_path',1,'svc'),Probe('verify_A',1,'svc'),Probe('verify_B',1,'svc')]
        worlds=[
            world('A',1,2,{'read_path':(obs('a'),),'verify_A':(obs('a2'),),'verify_B':()}),
            world('B',1,2,{'read_path':(obs('b'),),'verify_A':(),'verify_B':(obs('b2'),)})]
        plan=solve_adaptive(goals,probes,worlds,2)
        nonadaptive=evaluate_fixed(goals,probes,worlds,2)
        self.assertEqual(plan.decision.query,'read_path')
        self.assertEqual((plan.decision.expected_goal_value,plan.decision.expected_query_cost),(F(10),F(2)))
        self.assertEqual(nonadaptive[0],F(5))
        self.assertEqual(expected_replay(plan,worlds,probes,goals),(F(10),F(2)))
        self.assertEqual(execute_policy(plan,worlds[0],probes,goals)[2],('read_path','verify_A'))
        self.assertEqual(execute_policy(plan,worlds[1],probes,goals)[2],('read_path','verify_B'))

    def test_indistinguishable_worlds_cannot_leak_latent_labels(self):
        goals=[Goal('only',(need('secret'),),5)]
        probes=[Probe('get',1,'svc')]
        worlds=[world('hidden_A',1,2,{'get':()}),world('hidden_B',1,2,{'get':()})]
        plan=solve_adaptive(goals,probes,worlds,1)
        self.assertIsNone(plan.decision.query)
        self.assertEqual(plan.decision.expected_goal_value,0)

    def test_newer_authority_evidence_can_override_older_denial(self):
        goals=[Goal('allowed',(need('consent'),),10)]
        probes=[Probe('fresh',1,'svc')]
        worlds=[world('a',1,2,{'fresh':(obs('consent',at=60),)}),
                world('b',1,2,{'fresh':(obs('consent',value='no',at=60),)})]
        initial=(obs('consent',value='no',at=20),)
        plan=solve_adaptive(goals,probes,worlds,1,initial)
        self.assertEqual(plan.decision.expected_goal_value,F(5))
        self.assertEqual(expected_replay(plan,worlds,probes,goals,initial)[0],F(5))

    def test_equal_time_conflict_is_not_verified(self):
        goals=[Goal('one',(need('A'),),4)]
        probes=[Probe('q',1,'svc')]
        worlds=[world('x',1,1,{'q':(obs('A','svc','yes',50),)})]
        plan=solve_adaptive(goals,probes,worlds,1,(obs('A','svc','no',50),))
        self.assertEqual(plan.decision.expected_goal_value,0)

    def test_exact_query_cost_tie_break_stops_when_proof_already_present(self):
        goals=[Goal('goal',(need('A'),),9)]
        probes=[Probe('q',1,'svc')]
        worlds=[world('w',1,1,{'q':(obs('A'),)})]
        p=solve_adaptive(goals,probes,worlds,1,(obs('A'),))
        self.assertIsNone(p.decision.query)
        self.assertEqual(p.decision.expected_query_cost,0)

    def test_unsafe_query_and_spoofed_channel_rejected(self):
        with self.assertRaises(ValueError):Probe('danger',1,'svc',False)
        goals=[Goal('g',(need('e'),),1)]
        probes=[Probe('p',1,'svc')]
        worlds=[world('a',1,1,{'p':(obs('e',issuer='attacker'),)})]
        with self.assertRaisesRegex(ValueError,'service-bound'):
            solve_adaptive(goals,probes,worlds,1)

    def test_invalid_priors_rejected(self):
        g=[Goal('x',(need('x'),),1)];q=[Probe('p',1,'svc')]
        ws=[world('w',2,3,{'p':()})]
        with self.assertRaisesRegex(ValueError,'normalized'):
            solve_adaptive(g,q,ws,2)

    def test_probe_response_canonical_order_independent(self):
        a=(obs('a'),obs('b'))
        b=tuple(reversed(a))
        self.assertEqual(response_id(a),response_id(b))

    def test_120_discrete_latent_world_problems_exact_replay_and_openloop_bound(self):
        for seed in range(120):
            rng=random.Random(202611241+seed)
            count=rng.randint(2,5)
            probs=[Probe('q'+str(i),rng.randint(1,3),'svc') for i in range(count)]
            tokens=['token'+str(i) for i in range(count)]
            goals=[]
            for g in range(rng.randint(2,4)):
                chosen=rng.sample(tokens,rng.randint(1,min(3,len(tokens))))
                goals.append(Goal('g'+str(g),tuple(need(t) for t in chosen),rng.randint(1,10)))
            worlds=[]
            weights=[rng.randint(1,9) for _ in range(3)];total=sum(weights)
            for j in range(3):
                responses={}
                for p in probs:
                    selected=rng.sample(tokens,rng.randint(0,min(2,len(tokens))))
                    responses[p.name]=tuple(obs(t,value=rng.choice(['yes','yes','no']),at=rng.randint(10,90)) for t in selected)
                worlds.append(world('w'+str(j),weights[j],total,responses))
            budget=rng.randint(0,6)
            policy=solve_adaptive(goals,probs,worlds,budget)
            exp,cost=expected_replay(policy,worlds,probs,goals)
            fixed_value,_,_=evaluate_fixed(goals,probs,worlds,budget)
            self.assertEqual(exp,policy.decision.expected_goal_value,seed)
            self.assertEqual(cost,policy.decision.expected_query_cost,seed)
            self.assertGreaterEqual(exp,fixed_value,seed)
            self.assertLessEqual(cost,budget)


if __name__=='__main__':unittest.main()

class AdaptiveOracleIndependentTests(unittest.TestCase):
    def test_60_world_sets_match_uncached_full_policy_enumeration(self):
        from capegraph.adaptive import brute_force_adaptive_oracle
        for seed in range(60):
            rng=random.Random(202612200+seed)
            n=rng.randint(2,4)
            probes=[Probe(f'q{j}',rng.randint(1,3),'svc') for j in range(n)]
            goals=[Goal(f'goal{k}',tuple(need(f'e{i}') for i in rng.sample(range(4),rng.randint(1,3))),rng.randint(2,8)) for k in range(3)]
            worlds=[]
            weights=[rng.randint(1,4) for _ in range(3)];total=sum(weights)
            for i in range(3):
                rs={q.name:tuple(obs(f'e{j}',value=rng.choice(['yes','no']),at=rng.randint(10,80)) for j in rng.sample(range(4),rng.randint(0,2))) for q in probes}
                worlds.append(world(f'w{i}',weights[i],total,rs))
            budget=rng.randint(0,5)
            dp=solve_adaptive(goals,probes,worlds,budget)
            brute=brute_force_adaptive_oracle(goals,probes,worlds,budget)
            self.assertEqual((dp.decision.expected_goal_value,dp.decision.expected_query_cost),brute,f'seed {seed}')
