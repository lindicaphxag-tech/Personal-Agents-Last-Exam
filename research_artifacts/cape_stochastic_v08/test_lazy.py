import unittest, random
from cape_lazy import *
from cape_s import Model, solve as exact, independent_lp
from benchmark import random_model
from experiment_lazy import sensors

class LazyTests(unittest.TestCase):
    def test_oracles(self):
        for i in range(60):
            m=random_model(i);a=solve(m,batch=3);e=exact(m);ref,_=independent_lp(m)
            self.assertTrue(verify(m,a));self.assertEqual(a['L'],a['U']);self.assertEqual(a['L'],e['L']);self.assertAlmostEqual(float(a['L']),ref,places=7)
    def test_partial_anytime(self):
        m=sensors(7,3,False);e=exact(m);a=solve(m,max_expansions=32);self.assertTrue(verify(m,a));self.assertLessEqual(a['L'],e['L']);self.assertLessEqual(e['U'],a['U'])
        h=a['history'];self.assertEqual([r['L'] for r in h],sorted(r['L'] for r in h));self.assertEqual([r['U'] for r in h],sorted((r['U'] for r in h),reverse=True))
    def test_pair_bound_dominates_clair(self):
        for i in range(60):
            m=random_model(i);a=solve(m,max_expansions=0);b=solve(m,max_expansions=0,mode='clair');self.assertLessEqual(a['U'],b['U']);self.assertEqual(a['L'],b['L']);self.assertTrue(verify(m,a))
    def test_signed_reward_and_caps(self):
        rng=random.Random(71)
        for i in range(40):
            base=random_model(i);m=Model(base.priors,base.likelihood,tuple(tuple(F(rng.randrange(-4,5),3) for _ in range(3)) for _ in range(4)),(2,1),(1,2),3)
            e=exact(m);a=solve(m,max_expansions=2);self.assertTrue(verify(m,a));self.assertLessEqual(a['L'],e['L']);self.assertLessEqual(e['U'],a['U'])
    def test_zero_budget_randomization(self):
        m=Model(((1,0),(0,1)),(),((1,0),(0,1)),(),(),0);a=solve(m);self.assertEqual(a['L'],F(1,2));self.assertEqual(a['U'],F(1,2))
    def test_perfect(self):
        m=sensors(8,4);a=solve(m,max_expansions=1);self.assertEqual(a['L'],1);self.assertEqual(a['U'],1);self.assertEqual(a['history'][-1]['nodes'],18)
    def test_tamper(self):
        m=random_model(0);a=solve(m);a['U']+=F(1,3);self.assertFalse(verify(m,a))
    def test_tamper_dual(self):
        m=random_model(1);a=solve(m);a['upper']['dual']=(F(2),F(-1),F(0));self.assertFalse(verify(m,a))
    def test_tamper_graph(self):
        m=random_model(2);a=solve(m);a['lower']['expanded']=frozenset({((0,0),(1,1,1),999)});self.assertFalse(verify(m,a))
    def test_zero_mass_world(self):
        m=Model(((1,0,0),(0,1,0)),(((1,0,0),(0,1,1)),),((1,0,0),(0,1,0),(0,0,1)),(1,),(1,),1);a=solve(m);self.assertTrue(verify(m,a));self.assertEqual(a['L'],1);self.assertEqual(a['U'],1)
if __name__=='__main__':unittest.main()
