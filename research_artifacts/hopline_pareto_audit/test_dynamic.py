import unittest,random
from temporal import Walk,Ride
from dynamic import Base,cut_windows,union
from collections import deque
from benchmark import audit

def oracle(w,r,s,t,start,H,B,K,first,wait,sf,est):
    q=deque([(s,start,0,0)]);seen=set(q);best=None
    while q:
        u,tm,d,k=q.popleft()
        if u==t:
            val=(d,k);best=val if best is None else min(best,val);continue
        nxt=[]
        if u in wait:nxt.append((u,tm+1,d,k))
        for e in (*w,*r):
            if e.u!=u or sf and not e.step_free or not est and e.estimated:continue
            if isinstance(e,Walk):
                if any(a<=tm<b and tm+e.duration<=b for a,b in e.windows):nxt.append((e.v,tm+e.duration,d+e.distance,k))
            elif tm==e.depart and (k or tm<=first):nxt.append((e.v,e.arrive,d,k+1))
        for x in nxt:
            if x[1]<=H and x[2]<=B and x[3]<=K and x not in seen:seen.add(x);q.append(x)
    return best

def obj(v):return None if v is None else (v['distance'],v['rides'])

class DynamicTest(unittest.TestCase):
    def test_retimed_witness(self):
        w=[Walk('a','s','x',1,1,((0,10),)),Walk('b','x','t',1,1,((0,10),))]
        p=Base(w,[],'t',0,10,2,0,0,{'s','x'});u=p.restrict({'b':[(0,5)]})
        got=u.query('s',0,2);self.assertEqual(obj(got),(2,0));self.assertEqual(got['arrival'],6);self.assertEqual(u.stats['reused'],1)
        audit(got,u.walks,u.rides,'s','t',0,10,2,0,0,u.waitable,True,False)
    def test_hidden_dominated_alternative(self):
        w=[Walk('a','s','t',1,1,((0,10),)),Walk('b','s','t',2,2,((0,10),))]
        p=Base(w,[],'t',0,10,3,0,0,{'s'});u=p.restrict(removed=['a'])
        self.assertEqual(obj(u.query('s',0,3)),(2,0));self.assertEqual(u.stats['fallback'],1)
        self.assertEqual(obj(p.index.query('s',0,3)),(1,0))
    def test_ride_removal(self):
        p=Base([Walk('w','s','t',2,2,((0,10),))],[Ride('r','s','t',1,2)],'t',0,10,3,1,2,{'s'});u=p.restrict(removed=['r']);self.assertEqual(obj(u.query('s',0,3)),(2,0))
    def test_old_infeasible(self):
        p=Base([Walk('w','s','t',2,2,((0,10),))],[],'t',0,10,3,0,0,{'s'});u=p.restrict();self.assertIsNone(u.query('s',0,1));self.assertEqual(u.stats['old_infeasible'],1)
    def test_no_wait(self):
        p=Base([Walk('w','s','t',2,2,((0,10),))],[],'t',0,10,3,0,0,set());u=p.restrict({'w':[(0,5)]});self.assertIsNone(u.query('s',0,3));self.assertEqual(obj(u.query('s',5,3)),(2,0))
    def test_nonmerged_windows(self):
        self.assertEqual(cut_windows(((0,3),(3,6)),((1,2),)),((0,1),(2,3),(3,6)))
        self.assertEqual(union([(1,2),(4,6)]),((1,2),(4,6)))
    def test_invalid_update(self):
        p=Base([],[],'t',0,5,3,0,0,set());self.assertRaises(ValueError,p.restrict,{'x':[(0,1)]});self.assertRaises(ValueError,p.restrict,removed=['x'])
    def test_independent_snapshots(self):
        w=[Walk('a','s','t',1,1,((0,10),)),Walk('b','s','t',2,2,((0,10),))]
        p=Base(w,[],'t',0,10,3,0,0,{'s'});a=p.restrict(removed=['a']);b=p.restrict(removed=['b'])
        self.assertEqual(obj(a.query('s',0,3)),(2,0));self.assertEqual(obj(b.query('s',0,3)),(1,0));self.assertEqual(obj(a.query('s',0,3)),(2,0))
    def test_first_boarding(self):
        w=[Walk('a','s','x',1,1,((0,10),))];r=[Ride('r','x','t',2,3)]
        p=Base(w,r,'t',0,10,3,1,2,{'s','x'});u=p.restrict({'a':[(0,2)]})
        self.assertIsNone(u.query('s',0,3));self.assertEqual(u.stats['fallback'],1)
    def test_zero_duration_closure(self):
        p=Base([Walk('w','s','t',0,0,((0,5),))],[],'t',0,5,0,0,0,set());u=p.restrict({'w':[(1,2)]})
        self.assertIsNone(u.query('s',1,0));self.assertEqual(u.query('s',2,0)['arrival'],2)
    def test_random(self):
        rng=random.Random(20261127);stats=dict(reused=0,fallback=0,old_infeasible=0)
        for i in range(1800):
            ns=list(map(str,range(rng.randrange(2,7))));H=rng.randrange(5,16);B=rng.randrange(12);K=rng.randrange(4);first=rng.randrange(H+1);sf=bool(rng.randrange(2));est=bool(rng.randrange(2));w=[];r=[]
            for u in ns:
                for v in ns:
                    if u==v:continue
                    if rng.random()<.35:
                        ws=[]
                        for _ in range(rng.randrange(1,4)):
                            a=rng.randrange(H+1);ws.append((a,rng.randrange(a+1,H+2)))
                        w.append(Walk('w'+str(len(w)),u,v,rng.randrange(5),rng.randrange(5),tuple(ws),rng.random()<.8,rng.random()<.2))
                    if rng.random()<.18:
                        a=rng.randrange(H+1);r.append(Ride('r'+str(len(r)),u,v,a,rng.randrange(a,H+1),rng.random()<.8,rng.random()<.2))
            nodes={ns[-1]}|{v for e in (*w,*r) for v in (e.u,e.v)};wait={v for v in nodes if rng.random()<.5}
            p=Base(w,r,ns[-1],0,H,B,K,first,wait,step_free=sf,allow_estimates=est)
            for _ in range(2):
                removed=[e.id for e in (*w,*r) if rng.random()<.15];cuts={}
                for e in w:
                    if rng.random()<.25:
                        a=rng.randrange(H+1);cuts[e.id]=[(a,rng.randrange(a+1,H+2))]
                u=p.restrict(cuts,removed)
                for j in range(3):
                    s=rng.choice(ns);start=rng.randrange(H+1);b=rng.randrange(B+1);k=rng.randrange(K+1)
                    want=oracle(u.walks,u.rides,s,ns[-1],start,H,b,k,first,u.waitable,sf,est);got=u.query(s,start,b,k)
                    self.assertEqual(obj(got),want,(i,j,removed,cuts));audit(got,u.walks,u.rides,s,ns[-1],start,H,b,k,first,u.waitable,sf,est)
                for k in stats:stats[k]+=u.stats[k]
        print('RANDOM 10800',stats)
if __name__=='__main__':unittest.main()
