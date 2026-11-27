"""Reverse interval certificates for repeated fixed-deadline temporal queries.

Objective: minimum distance, then suffix ride count, subject to arrival by
one fixed deadline. Not an earliest-arrival solver. No arbitrary waiting.
"""
from dataclasses import dataclass
from heapq import heappush, heappop
from itertools import count
from types import MappingProxyType
from joint import prepare
from goal import uncovered
from temporal import Walk,Ride

@dataclass(frozen=True)
class Back:
    node: str
    lo: int
    hi: int
    prior: int
    distance: int
    rides: int
    raw_lo: int
    tail: 'Back | None'
    edge: 'Walk | Ride | None'

@dataclass(frozen=True)
class DeadlineIndex:
    target: str
    start: int
    deadline: int
    budget: int
    max_rides: int
    first_by: int
    waitable: frozenset
    labels: object
    expanded: int

    def query(self,source,time,budget,max_rides=None):
        if max_rides is None:max_rides=self.max_rides
        if any(type(x) is not int for x in (time,budget,max_rides)) or not self.start<=time<=self.deadline or not 0<=budget<=self.budget or not 0<=max_rides<=self.max_rides:
            raise ValueError('query outside index envelope')
        # Index state is prior ride count relative to the compiled maximum.
        # A smaller query ride cap is enforced by the stored suffix count.
        choices=[l for l in self.labels.get((source,0),()) if l.lo<=time<=l.hi and l.distance<=budget and l.rides<=max_rides]
        if not choices:return None
        l=min(choices,key=lambda x:(x.distance,x.rides));d,k=l.distance,l.rides;actions=[];tm=time
        while l.tail is not None:
            e=l.edge;a=max(tm,l.raw_lo)
            if isinstance(e,Walk):b=a+e.duration;actions.append(('walk',e.id,a,b))
            else:a=e.depart;b=e.arrive;actions.append(('ride',e.id,a,b))
            tm=b;l=l.tail
        return dict(arrival=tm,distance=d,rides=k,actions=actions)


def build_deadline(walks,rides,target,start,deadline,budget,max_rides,first_by,waitable,*,step_free=True,allow_estimates=False):
    if any(type(x) is not int for x in (start,deadline,budget,max_rides,first_by)) or not 0<=start<=deadline or min(budget,max_rides)<0:raise ValueError('invalid limits')
    p=prepare(walks,rides,target,budget,max_rides,deadline-start,step_free=step_free,allow_estimates=allow_estimates,build_joint=False)
    waitable=frozenset(waitable)
    if not waitable<=set(p.out):raise ValueError('unknown wait node')
    incoming={v:[] for v in p.out}
    for es in p.out.values():
        for e in es:incoming[e.v].append(e)
    labels={};q=[];serial=count();expanded=0
    def add(v,lo,hi,prior,d,r,tail,edge):
        if d>budget or prior+r>max_rides:return
        lo=max(lo,start);hi=min(hi,deadline)
        if lo>hi:return
        raw_lo=lo
        if v in waitable:lo=start
        f=labels.setdefault((v,prior),[])
        # Componentwise resource dominance is required because a query can
        # request a smaller ride budget than the compiled index.
        for a,b in uncovered(lo,hi,[(x.lo,x.hi) for x in f if x.distance<=d and x.rides<=r]):
            l=Back(v,a,b,prior,d,r,raw_lo,tail,edge);f.append(l);heappush(q,(d,r,next(serial),l))
    for k in range(max_rides+1):add(target,start,deadline,k,0,0,None,None)
    while q:
        _,_,_,l=heappop(q);expanded+=1
        for e in incoming[l.node]:
            if isinstance(e,Walk):
                for a,b in e.windows:
                    lo=max(a,l.lo-e.duration);hi=min(b-1,b-e.duration,l.hi-e.duration)
                    add(e.u,lo,hi,l.prior,l.distance+e.distance,l.rides,l,e)
            elif l.prior>0 and l.lo<=e.arrive<=l.hi and (l.prior>1 or e.depart<=first_by):
                add(e.u,e.depart,e.depart,l.prior-1,l.distance,l.rides+1,l,e)
    return DeadlineIndex(target,start,deadline,budget,max_rides,first_by,waitable,MappingProxyType({k:tuple(v) for k,v in labels.items()}),expanded)
