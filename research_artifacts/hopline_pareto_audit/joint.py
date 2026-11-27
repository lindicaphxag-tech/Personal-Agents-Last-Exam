"""Reusable reverse resource-constrained relaxation for exact temporal routing.

Profiles contain nondominated (time, distance, rides) of static suffixes,
not actual schedules. Profiles are built from immutable tuples of edges.
"""
from dataclasses import dataclass
from heapq import heappush, heappop
from itertools import count
from math import inf
from types import MappingProxyType
from temporal import Walk, Ride
from goal import Span, uncovered, reverse_bounds
from range_index import Coverage


def objective(r):
    return None if r is None else tuple(r[k] for k in ('arrival','distance','rides'))


@dataclass(frozen=True)
class Profile:
    walks: tuple
    rides: tuple
    target: str
    budget: int
    max_rides: int
    max_duration: int
    step_free: bool
    allow_estimates: bool
    out: object
    independent: tuple
    front: object
    expanded: int

    def suffix(self, node, distance, rides):
        """Earliest possible static suffix, subject to both remaining budgets."""
        for t,d,k in self.front.get(node, ()):
            if d <= distance and k <= rides:
                return t
        return inf


def prepare(walks, rides, target, budget, max_rides, max_duration, *,
            step_free=True, allow_estimates=False, build_joint=True):
    if any(type(x) is not int or x<0 for x in (budget,max_rides,max_duration)):
        raise ValueError('invalid profile limits')
    walks,rides=tuple(walks),tuple(rides)
    if len({e.id for e in (*walks,*rides)})!=len(walks)+len(rides):
        raise ValueError('duplicate edge identity')
    nodes={target}|{x for e in (*walks,*rides) for x in (e.u,e.v)}
    out={n:[] for n in nodes};rev={n:[] for n in nodes}
    for e in (*walks,*rides):
        if isinstance(e,Walk):
            if any(type(x) is not int or x<0 for x in (e.duration,e.distance)) or any(type(a) is not int or type(b) is not int or a>=b for a,b in e.windows):
                raise ValueError('invalid walk')
            cost=(e.duration,e.distance,0)
        elif isinstance(e,Ride):
            if type(e.depart) is not int or type(e.arrive) is not int or e.arrive<e.depart:raise ValueError('invalid ride')
            cost=(e.arrive-e.depart,0,1)
        else:raise ValueError('unknown edge')
        if (step_free and not e.step_free) or (not allow_estimates and e.estimated):continue
        out[e.u].append(e);rev[e.v].append((e.u,cost))
    front={n:[] for n in nodes};q=[];ids=count();expanded=0
    def add(v,t,d,k):
        if t>max_duration or d>budget or k>max_rides:return
        f=front[v]
        if any(a<=t and b<=d and c<=k for a,b,c in f):return
        f[:]=[(a,b,c) for a,b,c in f if not (t<=a and d<=b and k<=c)]
        f.append((t,d,k));heappush(q,(t,d,k,next(ids),v))
    if build_joint:add(target,0,0,0)
    while q:
        t,d,k,_,v=heappop(q)
        if (t,d,k) not in front[v]:continue
        expanded+=1
        for u,(a,b,c) in rev[v]:add(u,t+a,d+b,k+c)
    return Profile(walks,rides,target,budget,max_rides,max_duration,step_free,allow_estimates,
                   MappingProxyType({v:tuple(es) for v,es in out.items()}),
                   tuple(MappingProxyType(x) for x in reverse_bounds(out,target)),
                   MappingProxyType({v:tuple(sorted(f)) for v,f in front.items()}),expanded)


def solve_prepared(p,source,start,horizon,budget,max_rides,first_by,waitable,*,joint=True,use_index=False,min_distance=False):
    """Exact forward interval search, with profile bounds or independent bounds.

    Reuse only on the same immutable network/target and within profile limits.
    All bound preprocessing is charged separately in batched benchmarks.
    """
    if any(type(x) is not int for x in (start,horizon,budget,max_rides,first_by)) or not 0<=start<=horizon or not 0<=budget<=p.budget or not 0<=max_rides<=p.max_rides or horizon-start>p.max_duration:
        raise ValueError('query outside profile envelope')
    if joint and not p.front[p.target]:raise ValueError('joint profile not built')
    waitable=set(waitable)
    if not waitable<=set(p.out)|{source}:raise ValueError('unknown wait node')
    lt,ld,lk=p.independent
    seen={};queue=[];serial=count();expanded=generated=peak=pruned=0;cache={}
    def add(node,lo,hi,d,k,parent,edge):
        nonlocal generated,peak,pruned
        if node not in lt or d+ld[node]>budget or k+lk[node]>max_rides:return
        if joint:
            key=(node,d,k)
            if key not in cache:cache[key]=p.suffix(node,budget-d,max_rides-k)
            lower=cache[key]
        else:lower=lt[node]
        latest=horizon-lower
        hi=min(hi,latest)
        if lo>hi:
            pruned+=1;return
        raw_hi=hi
        if node in waitable and node!=p.target:hi=latest
        key=node,k
        if use_index:
            if key not in seen:seen[key]=Coverage(start,horizon)
            improved=seen[key].improve(lo,hi,d)
        else:
            old=seen.setdefault(key,[])
            improved=list(uncovered(lo,hi,[(x.lo,x.hi) for x in old if x.distance<=d]))
        for a,b in improved:
            l=Span(node,a,b,d,k,raw_hi,parent,edge)
            if not use_index:old.append(l)
            priority=(d+ld[node],k+lk[node],a+lower) if min_distance else (a+lower,d+ld[node],k+lk[node])
            heappush(queue,(*priority,next(serial),l));generated+=1
        peak=max(peak,len(queue))
    add(source,start,start,0,0,None,None)
    while queue:
        _,_,_,_,l=heappop(queue);expanded+=1
        if l.node==p.target:
            actions=[];cur=l;tm=l.lo
            while cur.parent is not None:
                arrival=min(tm,cur.raw_hi);e=cur.edge
                if isinstance(e,Walk):
                    depart=arrival-e.duration;actions.append(('walk',e.id,depart,arrival))
                else:
                    depart=e.depart;actions.append(('ride',e.id,depart,e.arrive))
                cur=cur.parent;tm=depart
            return dict(arrival=l.lo,distance=l.distance,rides=l.rides,actions=actions[::-1],expanded=expanded,generated=generated,peak_queue=peak,pruned=pruned)
        for e in p.out[l.node]:
            if isinstance(e,Walk):
                for a,b in e.windows:
                    lo=max(a,l.lo);hi=min(l.hi,b-1,b-e.duration)
                    if lo<=hi:add(e.v,lo+e.duration,hi+e.duration,l.distance+e.distance,l.rides,l,e)
            elif l.lo<=e.depart<=l.hi and (l.rides or e.depart<=first_by):
                add(e.v,e.arrive,e.arrive,l.distance,l.rides+1,l,e)
    return None
