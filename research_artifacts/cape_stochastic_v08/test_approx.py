import unittest, random
from cape_approx import *
from cape_s import solve as exact, independent_lp
from benchmark import random_model, repeated

class ApproxTests(unittest.TestCase):
    def test_exact_convex_decomposition(self):
        rng=random.Random(20261124)
        for n in range(2,8):
            for _ in range(100):
                a=[rng.randrange(20) for _ in range(n)];a[0]+=1;q=tuple(F(x,sum(a)) for x in a)
                K=n*rng.randrange(1,12);s=split(q,K)
                self.assertLessEqual(len(s),n)
                self.assertEqual(tuple(sum(weight*F(v[i],K) for v,weight in s) for i in range(n)),q)
                v=representative(q,K);self.assertEqual(sum(v),K);self.assertEqual(tuple(x>0 for x in v),tuple(x>0 for x in q))
    def test_exact_oracles(self):
        for seed in range(60):
            m=random_model(seed); e=exact(m);a=solve_repaired(m,12);r,_=independent_lp(m)
            self.assertEqual(e['L'],e['U']);self.assertAlmostEqual(float(e['L']),r,places=7)
            self.assertLessEqual(a['L'],e['L']);self.assertLessEqual(e['U'],a['U']);self.assertTrue(verify(m,a))
            self.assertEqual(a['repair_trace'],sorted(a['repair_trace']))
    def test_transition_mass(self):
        for seed in range(20):
            m=random_model(seed)
            for relax in [False,True]:
                nodes,edges=compile_grid(m,12,relax)
                for s,out in enumerate(edges):
                    for a,children in out.items():
                        self.assertEqual(sum(k for _,_,k in children),1)
                        if relax:
                            for w,q in enumerate(nodes[s][1]):self.assertEqual(sum(k*F(nodes[t][1][w],12) for _,t,k in children),F(q,12))
    def test_tampering(self):
        m=repeated(3);a=solve(m,10);a['U']+=F(1,100);self.assertFalse(verify(m,a))
    def test_invalid_dual(self):
        m=repeated(3);a=solve(m,10);a['dual']=(F(-1),F(2));self.assertRaises(ValueError,verify,m,a)
    def test_anytime(self):
        m=random_model(6);l,u,rows=anytime(m,[3,6,12]);self.assertEqual(l['L'],max(x['L'] for x in rows));self.assertEqual(u['U'],min(x['U'] for x in rows));self.assertLessEqual(l['L'],u['U'])
    def test_randomization(self):
        m=repeated(0);a=solve_repaired(m,2);self.assertEqual(a['L'],F(1,2));self.assertEqual(a['U'],F(1,2))
    def test_zero_observation(self):
        m=Model(((F(1),F(0)),(F(0),F(1))),(((1,0),(0,1),(0,0)),),((1,0),(0,1)),(1,),(1,),1);a=solve_repaired(m,2);self.assertEqual(a['L'],1);self.assertEqual(a['U'],1)
if __name__=='__main__':unittest.main()
