"""Historical London network topology; all availability/resource overlays are synthetic."""
import csv,hashlib,random,time,json,statistics,sys
from pathlib import Path
from collections import defaultdict
from heapq import heappush,heappop
from temporal import Walk,Ride
from indexed import solve_indexed
from goal import solve_goal,reverse_bounds
from adaptive import solve_adaptive
from benchmark import audit
PIN='0fb34991739252164f8558731a5e97aa9a9c8aa3'
def read_edges(path):
    b=Path(path).read_bytes();assert hashlib.sha1(f'blob {len(b)}\0'.encode()+b).hexdigest()==PIN,'source blob mismatch'
    rows=[(r['station1'],r['station2'],int(r['line_id']),int(r['time'])) for r in csv.DictReader(b.decode().splitlines())]
    assert all(t>0 for _,_,_,t in rows)
    return rows

def explicit(walks,rides,s,t,start,H,B,K,first,waitable,sf=True,est=False,guided=False):
    out=defaultdict(list)
    for e in (*walks,*rides):
        if (not sf or e.step_free) and (est or not e.estimated):out[e.u].append(e)
    if guided:
        lt,ld,lk=reverse_bounds({v:out[v] for v in {s,t}|{x for e in (*walks,*rides) for x in (e.u,e.v)}},t)
    else:lt=ld=lk=defaultdict(int)
    def admissible(v,tt,dd,kk):
        return (not guided or v in lt) and tt+lt[v]<=H and dd+ld[v]<=B and kk+lk[v]<=K
    def key(v,tt,dd,kk):return (tt+lt[v],dd+ld[v],kk+lk[v],tt,dd,kk,v)
    if not admissible(s,start,0,0):return None,0
    best={(s,start,0):0};q=[key(s,start,0,0)];expanded=0
    while q:
        _,_,_,tm,d,k,u=heappop(q)
        if d!=best[(u,tm,k)]:continue
        expanded+=1
        if u==t:return (tm,d,k),expanded
        nxt=[]
        if u in waitable:nxt.append((u,tm+1,d,k))
        for e in out[u]:
            if isinstance(e,Walk):
                if any(a<=tm<b and tm+e.duration<=b for a,b in e.windows):nxt.append((e.v,tm+e.duration,d+e.distance,k))
            elif tm==e.depart and (k or tm<=first):nxt.append((e.v,e.arrive,d,k+1))
        for v,tt,dd,kk in nxt:
            if admissible(v,tt,dd,kk) and dd<best.get((v,tt,kk),B+1):
                best[v,tt,kk]=dd;heappush(q,key(v,tt,dd,kk))
    return None,expanded

def scenario(rows,seed,mode):
    rng=random.Random(seed);nodes=sorted({u for a,b,_,_ in rows for u in (a,b)});H=75;B=rng.choice([20,35,55]);K=2 if mode=='mixed_rides' else 0
    walks=[];rides=[]
    for i,(u,v,line,t) in enumerate(rows):
        dist=rng.randint(1,5); sf=rng.random()>.06
        if mode=='static': win=((0,H+1),)
        else:
            a=rng.randrange(8,42);b=a+rng.randrange(5,18)
            win=((0,a),(b,H+1)) if rng.random()<.55 else ((0,H+1),)
        for j,(a,b) in enumerate(((u,v),(v,u))):
            walks.append(Walk(f'w{i}-{j}',a,b,t,dist,win,sf))
            if mode=='mixed_rides' and i%13==0:
                for dep in range(rng.randrange(8),H-t+1,12):rides.append(Ride(f'r{i}-{j}-{dep}',a,b,dep,dep+t,sf))
    waitable=set(nodes) if mode=='static' else {v for v in nodes if rng.random()<.4}
    s,t=rng.sample(nodes,2);waitable.add(s)
    return (walks,rides,s,t,0,H,B,K,25,waitable)

def run(path,n=120,seed=20261127):
    rows=read_edges(path);modes=('static','mixed_windows','mixed_rides');res={m:dict(cases=0,reachable=0,oracle_expanded=0,index_expanded=0,goal_expanded=0,oracle_ns=0,index_ns=0,goal_ns=0,goal_faster=0,adaptive_ns=0,adaptive_expanded=0,astar_ns=0,astar_expanded=0,goal_faster_adaptive=0,list_ns=0,list_expanded=0) for m in modes}
    records=[]
    for i in range(n):
        mode=modes[i%3];args=scenario(rows,seed+i,mode);r=res[mode];r['cases']+=1
        t=time.perf_counter_ns();want,expanded=explicit(*args);r['oracle_ns']+=time.perf_counter_ns()-t;r['oracle_expanded']+=expanded
        t=time.perf_counter_ns();astar,ae=explicit(*args,guided=True);r['astar_ns']+=time.perf_counter_ns()-t;r['astar_expanded']+=ae
        assert astar==want
        times={};counts={}
        for name,fn in ([('index',lambda *a:solve_indexed(*a,hybrid=False)),('adaptive',solve_adaptive),('list',lambda *a:solve_goal(*a,use_index=False)),('goal',solve_goal)] if i%2==0 else [('goal',solve_goal),('list',lambda *a:solve_goal(*a,use_index=False)),('adaptive',solve_adaptive),('index',lambda *a:solve_indexed(*a,hybrid=False))]):
            t=time.perf_counter_ns();got=fn(*args);times[name]=time.perf_counter_ns()-t;r[name+'_ns']+=times[name]
            assert (None if got is None else tuple(got[k] for k in ('arrival','distance','rides')))==want,(i,mode,want,got)
            audit(got,*args,True,False)
            if got:r[name+'_expanded']+=got['expanded'];counts[name]=got['expanded']
        r['goal_faster']+=times['goal']<times['index'];r['goal_faster_adaptive']+=times['goal']<times['adaptive'];r['reachable']+=want is not None
        records.append(dict(case=i,mode=mode,source=args[2],target=args[3],budget=args[6],reachable=want is not None,objective=want,expanded=counts,ns=times))
    return dict(source_blob=PIN,rows=len(rows),nodes=len({x for a,b,_,_ in rows for x in (a,b)}),cases=n,seed=seed,groups=res,records=records,scope='real historical station adjacency and listed traversal times; artificial windows, distance costs, wait permissions, accessibility and rides; not transit timetable or accessibility study')
if __name__=='__main__':print(json.dumps(run(sys.argv[1],int(sys.argv[2]) if len(sys.argv)>2 else 120),indent=2))
