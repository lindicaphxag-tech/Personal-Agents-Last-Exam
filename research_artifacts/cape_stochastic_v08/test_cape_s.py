import unittest, random
from cape_s import *
from benchmark import random_model, repeated

class Tests(unittest.TestCase):
    def test_sixty_seed_exact_oracle(self):
        for i in range(60):
            m=random_model(i); c=solve(m); ref,_=independent_lp(m)
            self.assertEqual(c['L'],c['U']); self.assertAlmostEqual(float(c['L']),ref,places=7); self.assertTrue(verify(m,c))
    def test_randomization_essential(self):
        m=repeated(0); c=solve(m); self.assertEqual(c['L'],F(1,2)); self.assertEqual(c['U'],F(1,2))
        self.assertEqual(max(min(sum(pw*v for pw,v in zip(p,r)) for p in m.priors) for r in enumerate_vectors(m)),0)
    def test_repeated_closed_form(self):
        from math import comb
        for b in range(1,12,2):
            c=solve(repeated(b)); expected=sum(comb(b,k)*F(4,5)**k*F(1,5)**(b-k) for k in range(b//2+1,b+1))
            self.assertEqual(c['L'],expected);self.assertEqual(c['U'],expected);self.assertEqual(len(c['nodes']),(b+1)*(b+2)//2)
    def test_probability_mass(self):
        for i in range(20):
            m=random_model(i); nodes,edges=graph(m)
            for s,out in enumerate(edges):
                r=nodes[s][1]; q=[F(x,sum(r)) for x in r]
                for a,children in out.items():
                    self.assertEqual(sum(k for _,_,k in children),1)
                    for w in range(len(q)):
                        self.assertEqual(sum(k*F(nodes[t][1][w],sum(nodes[t][1])) for _,t,k in children),q[w])
    def test_tampered_bound(self):
        m=repeated(3); c=solve(m); c['L']+=F(1,100); self.assertFalse(verify(m,c))
    def test_unknown_observation(self):
        m=repeated(3); c=solve(m); self.assertIsNone(execute(m,c,lambda a:99,random.Random(3).randrange))
    def test_adapter_error(self):
        def bad(a): raise RuntimeError()
        m=repeated(3); self.assertIsNone(execute(m,solve(m),bad,random.Random(4).randrange))
    def test_zero_likelihood_branch(self):
        m=Model(((F(1),F(0)),(F(0),F(1))),(((1,0),(0,1),(0,0)),),((1,0),(0,1)),(1,),(1,),1)
        c=solve(m);self.assertEqual(c['L'],1);self.assertEqual(c['U'],1);self.assertEqual(len(c['nodes']),3)
    def test_asymmetric_cost_budget(self):
        m=Model(((F(1),F(0)),(F(0),F(1))),(((1,0),(0,1)),((F(1,2),F(1,2)),(F(1,2),F(1,2)))),((1,0),(0,1)),(1,2),(3,1),2)
        c=solve(m);self.assertEqual(c['L'],F(1,2));self.assertTrue(all(0 not in e for e in c['edges']))
    def test_negative_rewards(self):
        m=Model(((F(1),F(0)),(F(0),F(1))),(),((-1,-2),(-2,-1)),(),(),0)
        c=solve(m);self.assertEqual(c['L'],F(-3,2));self.assertEqual(c['U'],F(-3,2))
    def test_duplicate_likelihood_child(self):
        m=Model(((F(1),F(0)),(F(0),F(1))),(((F(1,2),F(1,2)),(F(1,2),F(1,2))),),((1,0),(0,1)),(1,),(1,),1)
        c=solve(m);self.assertEqual(len(c['nodes']),2);self.assertEqual(c['L'],F(1,2));self.assertEqual(c['U'],F(1,2))
    def test_corrupted_dual(self):
        m=repeated(1); c=solve(m);c['dual']=(F(2),F(-1));self.assertRaises(AssertionError,verify,m,c)

if __name__=='__main__':unittest.main()
