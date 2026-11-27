import unittest, random
from temporal import Walk,Ride
from goal import solve_goal
from benchmark import oracle,audit

class GoalTest(unittest.TestCase):
    def test_distance_bound_infeasible(self):
        self.assertIsNone(solve_goal([Walk('a','s','t',1,3,((0,10),))],[],'s','t',0,10,2,0,0,{'s'}))
    def test_late_window(self):
        args=([Walk('a','s','x',1,1,((0,1001),)),Walk('b','x','t',1,1,((999,1000),))],[],'s','t',0,1000,2,0,0,{'s'})
        for index in (False,True):
            r=solve_goal(*args,use_index=index);self.assertEqual((r['arrival'],r['distance']), (1000,2));audit(r,*args,True,False)
    def test_source_goal(self):
        r=solve_goal([],[],'s','s',3,5,0,0,0,set());self.assertEqual((r['arrival'],r['distance'],r['rides']),(3,0,0))
    def test_no_ride_budget(self):
        self.assertIsNone(solve_goal([], [Ride('r','s','t',1,2)],'s','t',0,5,10,0,3,{'s'}))
    def test_estimate(self):
        args=([Walk('a','s','t',1,0,((0,5),),True,True)],[],'s','t',0,5,0,0,0,{'s'})
        self.assertIsNone(solve_goal(*args));self.assertEqual(solve_goal(*args,allow_estimates=True)['arrival'],1)
    def test_independent_random(self):
        rng=random.Random(20261201)
        for i in range(3000):
            nodes=list(map(str,range(rng.randint(2,7))));H=rng.randint(5,20);start=rng.randrange(H+1);B=rng.randrange(13);K=rng.randrange(4);first=rng.randrange(H+1);sf=bool(rng.randrange(2));est=bool(rng.randrange(2));w=[];r=[]
            for u in nodes:
                for v in nodes:
                    if u==v:continue
                    if rng.random()<.32:
                        windows=[]
                        for _ in range(rng.randint(1,3)):
                            a=rng.randrange(H+1);b=rng.randrange(a+1,H+2);windows.append((a,b))
                        w.append(Walk('w'+str(len(w)),u,v,rng.randrange(5),rng.randrange(5),tuple(windows),rng.random()<.8,rng.random()<.2))
                    if rng.random()<.2:
                        a=rng.randrange(H+1);r.append(Ride('r'+str(len(r)),u,v,a,rng.randrange(a,H+1),rng.random()<.8,rng.random()<.2))
            waitable={v for v in {nodes[0],nodes[-1]}|{x for e in (*w,*r) for x in (e.u,e.v)} if rng.random()<.5}
            args=(w,r,nodes[0],nodes[-1],start,H,B,K,first,waitable)
            want,_=oracle(*args,sf,est)
            for index in (True,False):
                got=solve_goal(*args,step_free=sf,allow_estimates=est,use_index=index)
                self.assertEqual(None if got is None else tuple(got[k] for k in ('arrival','distance','rides')),want,(i,index));audit(got,*args,sf,est)
if __name__=='__main__': unittest.main()
