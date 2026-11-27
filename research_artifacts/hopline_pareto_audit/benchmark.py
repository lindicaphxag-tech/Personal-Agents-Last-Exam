"""Independent explicit-state oracle; reproducible random graph experiment."""
import random, json, time
from collections import deque
from temporal import Walk,Ride,solve
from interval import solve_interval


def oracle(walks,rides,s,t,start,H,B,K,first,waitable,sf=True,est=False):
    initial=(s,start,0,0); todo=deque([initial]); seen={initial}; best=None
    while todo:
        u,tm,d,k=todo.popleft()
        if u==t:
            z=(tm,d,k); best=z if best is None else min(best,z); continue
        nxt=[]
        if u in waitable: nxt.append((u,tm+1,d,k))
        for e in walks:
            if e.u==u and (not sf or e.step_free) and (est or not e.estimated) and any(a<=tm<b and tm+e.duration<=b for a,b in e.windows):
                nxt.append((e.v,tm+e.duration,d+e.distance,k))
        for e in rides:
            if e.u==u and tm==e.depart and (k or tm<=first) and (not sf or e.step_free) and (est or not e.estimated):
                nxt.append((e.v,e.arrive,d,k+1))
        for z in nxt:
            if z[1]<=H and z[2]<=B and z[3]<=K and z not in seen:seen.add(z);todo.append(z)
    return best,len(seen)


def audit(result,walks,rides,s,t,start,H,B,K,first,waitable,sf,est):
    if result is None:return
    es={e.id:e for e in (*walks,*rides)};u=s;tm=start;d=k=0
    for kind,eid,a,b in result['actions']:
        assert a>=tm and (a==tm or u in waitable)
        if kind=='wait':assert eid==u and u in waitable and a==tm and b==a+1
        else:
            e=es[eid];assert e.u==u and (not sf or e.step_free) and (est or not e.estimated)
            if kind=='walk':
                assert isinstance(e,Walk) and b==a+e.duration and any(x<=a<y and b<=y for x,y in e.windows);d+=e.distance
            else:
                assert isinstance(e,Ride) and (a,b)==(e.depart,e.arrive) and (k or a<=first);k+=1
            u=e.v
        tm=b
    assert u==t and (tm,d,k)==(result['arrival'],result['distance'],result['rides']) and tm<=H and d<=B and k<=K


def run(n=6000,seed=20261127):
    rng=random.Random(seed); stats={k:dict(cases=0,reachable=0,oracle_states=0,oracle_reachable_states=0,solver_reachable_expanded=0,forced_time_reachable_expanded=0,interval_expanded=0,interval_generated=0,interval_peak=0) for k in ('all_wait','mixed_wait','no_wait')};t0=time.perf_counter()
    for i in range(n):
        nodes=[str(j) for j in range(rng.randrange(3,7))]; H=rng.randrange(8,21);B=rng.randrange(1,14);K=rng.randrange(0,4);first=rng.randrange(H+1);sf=bool(rng.randrange(2));est=bool(rng.randrange(2));mode=list(stats)[i%3]
        waitable=set(nodes) if mode=='all_wait' else {x for x in nodes if rng.random()<.5} if mode=='mixed_wait' else set()
        walks=[];rides=[]
        for u in nodes:
            for v in nodes:
                if u==v:continue
                if rng.random()<.37:
                    windows=[]
                    for _ in range(rng.randrange(1,4)):
                        a=rng.randrange(H);b=rng.randrange(a+1,H+2);windows.append((a,b))
                    walks.append(Walk('w'+str(len(walks)),u,v,rng.randrange(0,5),rng.randrange(0,6),tuple(windows),rng.random()<.8,rng.random()<.2))
                if rng.random()<.20:
                    a=rng.randrange(H+1);rides.append(Ride('r'+str(len(rides)),u,v,a,rng.randrange(a,H+1),rng.random()<.8,rng.random()<.2))
        waitable &= {nodes[0],nodes[-1]} | {x for e in (*walks,*rides) for x in (e.u,e.v)}
        args=(walks,rides,nodes[0],nodes[-1],0,H,B,K,first,waitable)
        want,states=oracle(*args,sf,est);got=solve(*args,step_free=sf,allow_estimates=est);actual=None if got is None else tuple(got[k] for k in ('arrival','distance','rides'))
        assert actual==want,(i,args,want,actual)
        audit(got,*args,sf,est);iv=solve_interval(*args,step_free=sf,allow_estimates=est);assert (None if iv is None else tuple(iv[k] for k in ('arrival','distance','rides')))==want,(i,args,want,iv);audit(iv,*args,sf,est);full=solve(*args,step_free=sf,allow_estimates=est,force_time_state=True);assert (None if full is None else tuple(full[k] for k in ('arrival','distance','rides')))==want;s=stats[mode];s['cases']+=1;s['oracle_states']+=states
        if iv:s['interval_expanded']+=iv['expanded'];s['interval_generated']+=iv['generated'];s['interval_peak']=max(s['interval_peak'],iv['peak_queue'])
        if got:s['reachable']+=1;s['oracle_reachable_states']+=states;s['solver_reachable_expanded']+=got['expanded'];s['forced_time_reachable_expanded']+=full['expanded']
    return {'seed':seed,'cases':n,'matched':n,'groups':stats,'wall_seconds':time.perf_counter()-t0,'note':'forced_time and solver use identical early termination; oracle enumerates all states; counts are not wall-clock speed'}
if __name__=='__main__':print(json.dumps(run(),indent=2))
