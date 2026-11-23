import unittest
from cape_approx import F,solve
from cape_s import Model
from runtime import execute_grid
class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.m=Model(((F(1),F(0)),(F(0),F(1))),(((1,0),(0,1)),),((1,0),(0,1)),(1,),(1,),1)
        self.c=solve(self.m,2)
    def test_correct(self):
        for w in (0,1):
            self.assertEqual(execute_grid(self.m,self.c,lambda _:w,lambda _:0)['decision'],w)
    def test_bad_obs(self):
        self.assertEqual(execute_grid(self.m,self.c,lambda _:99)['status'],'UNVERIFIED')
        self.assertEqual(execute_grid(self.m,self.c,lambda _:True)['status'],'UNVERIFIED')
    def test_adapter_failure(self):
        def bad(_):raise RuntimeError('unavailable')
        self.assertEqual(execute_grid(self.m,self.c,bad)['status'],'UNVERIFIED')
    def test_tampered_certificate(self):
        self.c['L']+=F(1,10)
        self.assertRaises(ValueError,execute_grid,self.m,self.c,lambda _:0)
if __name__=='__main__':unittest.main()
