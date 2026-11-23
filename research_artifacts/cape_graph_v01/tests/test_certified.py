"""Independent full-policy and adversarial certificate tests."""
from dataclasses import replace
from fractions import Fraction as F
import unittest, random
from capegraph import Goal,Need,Witness,World,Probe,Prior
from capegraph.adaptive import _setup
from capegraph.robust import _enumerate,_metrics
from capegraph.certified import EvidenceDAG,solve_certified,solve_flow,verify_certificate,verify_flow,execute_flow
from capegraph.mixed import solve_mixed
from experiments.certified_benchmark import branch_case,matrix_lp,extend

class CertifiedTests(unittest.TestCase):
    def test_branch_scaling_exact(self):
        for n in (2,3,4,6,8,12):
            p=branch_case(n,min(n,8));f=solve_flow(*p)
            self.assertEqual(verify_flow(f,*p),(F(5),F(5)))
    def test_exact_pricing_against_unpruned_full_trees(self):
        for seed in range(40):
            p=extend(2026120100+seed);g,q,w,b,ps=p
            gs,qs,ws,ini=_setup(g,q,w,b,());cs,_=_enumerate(gs,qs,ws,ini,b,prune=False)
            dag=EvidenceDAG(g,q,w,b);rng=random.Random(seed)
            a=[rng.randrange(0,5) for _ in ws];a[0]+=1
            weights=tuple(F(x,sum(a)) for x in a)
            col,val=dag.price(weights)
            self.assertEqual(val,max(sum((x*y for x,y in zip(weights,c.rewards)),F(0)) for c in cs))
    def test_flow_against_unpruned_full_policy_lp(self):
        for seed in range(50):
            p=extend(2026120200+seed);g,q,w,b,ps=p
            gs,qs,ws,ini=_setup(g,q,w,b,());cs,_=_enumerate(gs,qs,ws,ini,b,prune=False)
            value=matrix_lp([tuple(v for _,v in _metrics(c,ws,ps)[2]) for c in cs])
            f=solve_flow(*p); self.assertLessEqual(float(f.lower)-1e-7,value);self.assertGreaterEqual(float(f.upper)+1e-7,value)
    def test_two_prior_compatibility(self):
        for seed in range(24):
            g,q,w,b,ps=extend(2026120300+seed);p=(g,q,w,b,ps[-2:]);r=solve_mixed(*p);f=solve_flow(*p)
            self.assertLessEqual(f.lower,r.guaranteed_reward);self.assertGreaterEqual(f.upper,r.guaranteed_reward)
    def test_early_stop_is_valid_not_claimed_optimal(self):
        p=branch_case(8);r=solve_certified(*p,max_iterations=1,epsilon=F(0));self.assertEqual(r.reason,'iteration_cap');self.assertGreater(r.gap,0);self.assertLessEqual(r.lower,5);self.assertGreaterEqual(r.upper,5);verify_certificate(r,*p)
    def test_anytime_monotone_bounds(self):
        p=branch_case(4,4);r=solve_certified(*p);self.assertTrue(all(a[0]<=b[0]<=b[1]<=a[1] for a,b in zip(r.history,r.history[1:])))
    def test_tampered_flow_bounds(self):
        p=branch_case(3,3);r=solve_flow(*p)
        for bad in (replace(r,lower=r.lower+1),replace(r,upper=r.upper-1),replace(r,nature=(F(0),)*len(r.nature))):
            with self.assertRaises(ValueError):verify_flow(bad,*p)
    def test_tampered_policy_simplex(self):
        p=branch_case(3,3);r=solve_flow(*p);probs=list(r.probabilities);probs[-1]=(F(0),)*len(probs[-1])
        with self.assertRaises(ValueError):verify_flow(replace(r,probabilities=tuple(probs)),*p)
    def test_tampered_column_reward(self):
        p=branch_case(3,3);r=solve_certified(*p);x,c=r.support[0]
        with self.assertRaises(ValueError):verify_certificate(replace(r,support=((x,replace(c,rewards=tuple(v+1 for v in c.rewards))),)+r.support[1:]),*p)
    def test_permutation_invariant_canonical_dag(self):
        g,q,w,b,ps=branch_case(4,4);r=solve_flow(g,q,w,b,ps)
        self.assertEqual(verify_flow(r,tuple(reversed(g)),tuple(reversed(q)),tuple(reversed(w)),b,tuple(reversed(ps))),(F(5),F(5)))
    def test_zero_budget_and_initial_proof(self):
        g,q,w,b,ps=branch_case(4,4);r=solve_flow(g,q,w,0,ps,(Witness('proof','ok','service',1),))
        self.assertEqual((r.lower,r.upper),(F(10),F(10)));self.assertTrue(all(c==0 for c in r.scenario_costs))
    def test_shared_history_with_superseding_evidence(self):
        g=(Goal('goal',(Need('p','ok',('svc',),0,100),Need('q','ok',('svc',),0,100)),9),)
        q=(Probe('a',1,'svc'),Probe('b',1,'svc'),Probe('c',1,'svc'))
        w=(World('x',F(1,2),{'a':(Witness('p','ok','svc',1),),'b':(Witness('q','ok','svc',2),),'c':(Witness('p','bad','svc',3),)}),World('y',F(1,2),{'a':(Witness('p','ok','svc',1),),'b':(Witness('q','ok','svc',2),),'c':(Witness('p','ok','svc',3),)}))
        ps=(Prior('x',{'x':F(1),'y':F(0)}),Prior('y',{'x':F(0),'y':F(1)}));r=solve_flow(g,q,w,3,ps)
        self.assertEqual(verify_flow(r,g,q,w,3,ps),(F(9),F(9)))
    def test_caps_and_invalid_prior(self):
        p=branch_case(4,4)
        with self.assertRaises(ValueError):solve_flow(*p,max_nodes=2)
        with self.assertRaises(ValueError):solve_flow(*p[:-1],(Prior('invalid',{}),))
    def test_point_prior_zero_mass_branch(self):
        g,q,w,b,ps=branch_case(4,4);dag=EvidenceDAG(g,q,w,b);weights=(F(1),)+(F(0),)*(len(w)-1);c,v=dag.price(weights)
        self.assertEqual(v,10);self.assertTrue(all(x<=b for x in c.costs))
    def test_execution_without_world_id(self):
        g,q,w,b,ps=branch_case(4,4);dag=EvidenceDAG(g,q,w,b);r=solve_flow(g,q,w,b,ps)
        for world in w:
            rng=random.Random(512)
            for _ in range(16):
                run=execute_flow(dag,r,lambda probe: world.responses[probe.name],randbelow=rng.randrange)
                self.assertEqual(run.status,'COMPLETED');self.assertLessEqual(run.spent,b);self.assertEqual(len(run.queried),len(set(run.queried)))
    def test_execution_unknown_source_and_adapter_failure(self):
        g,q,w,b,ps=branch_case(4,4);dag=EvidenceDAG(g,q,w,b);r=solve_flow(g,q,w,b,ps)
        for result in ((Witness('group',999,'service',1),),(Witness('proof','ok','untrusted',2),),None):
            run=execute_flow(dag,r,lambda _: result,randbelow=lambda n:0)
            self.assertEqual(run.status,'UNVERIFIED');self.assertIsNone(run.reward);self.assertEqual(run.verified_goals,())
        def broken(_):raise ConnectionError('failed')
        self.assertEqual(execute_flow(dag,r,broken,randbelow=lambda n:0).status,'UNVERIFIED')
    def test_execution_invalid_policy_no_callbacks(self):
        g,q,w,b,ps=branch_case(4,4);dag=EvidenceDAG(g,q,w,b);r=solve_flow(g,q,w,b,ps)
        probs=list(r.probabilities);probs[-1]=(F(0),)*len(probs[-1]);seen=[]
        with self.assertRaises(ValueError):execute_flow(dag,replace(r,probabilities=tuple(probs)),lambda p:seen.append(p))
        self.assertEqual(seen,[])
if __name__=='__main__':unittest.main()
