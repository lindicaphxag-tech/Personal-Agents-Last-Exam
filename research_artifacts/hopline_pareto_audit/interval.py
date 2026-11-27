"""Exact interval reachability labels for discrete mixed-wait resource walks."""
from dataclasses import dataclass
from heapq import heappush, heappop
from itertools import count
from temporal import Walk, Ride

@dataclass(frozen=True)
class Span:
    node: str
    lo: int
    hi: int
    distance: int
    rides: int
    raw_hi: int
    parent: 'Span | None'
    edge: 'Walk | Ride | None'


def uncovered(lo, hi, covered):
    """Inclusive integer intervals minus the union of covered intervals."""
    for a,b in sorted(covered):
        if b < lo: continue
        if a > hi: break
        if a > lo: yield lo,a-1
        lo=max(lo,b+1)
        if lo>hi:return
    if lo<=hi:yield lo,hi


def solve_interval(walks, rides, source, target, start, horizon, budget, max_rides,
                   first_by, waitable, *, step_free=True, allow_estimates=False):
    """Exact under temporal.py's finite discrete-time walk semantics.

    A span represents every reachable integer time in [lo,hi] at identical
    resource cost. At a waitable node, suffix closure is legitimate; elsewhere
    only actual reachable times are included. Lower-distance coverage at the
    same node and ride count can remove overlapping times, never other times.
    """
    nums=(start,horizon,budget,max_rides,first_by)
    if any(type(x) is not int for x in nums) or not 0<=start<=horizon or min(budget,max_rides)<0: raise ValueError('invalid bounds')
    walks,rides=tuple(walks),tuple(rides)
    nodes={source,target}|{x for e in (*walks,*rides) for x in (e.u,e.v)}
    waitable=set(waitable)
    if not waitable<=nodes:raise ValueError('unknown wait node')
    if len({e.id for e in (*walks,*rides)})!=len(walks)+len(rides):raise ValueError('duplicate edge identity')
    out={n:[] for n in nodes}
    for e in walks:
        if type(e.duration) is not int or type(e.distance) is not int or min(e.duration,e.distance)<0:raise ValueError('invalid walk')
        if any(type(a) is not int or type(b) is not int or a>=b for a,b in e.windows):raise ValueError('invalid window')
        if (not step_free or e.step_free) and (allow_estimates or not e.estimated):out[e.u].append(e)
    for e in rides:
        if type(e.depart) is not int or type(e.arrive) is not int or e.arrive<e.depart:raise ValueError('invalid ride')
        if (not step_free or e.step_free) and (allow_estimates or not e.estimated):out[e.u].append(e)
    seen={};queue=[];serial=count();expanded=generated=peak=0
    def add(node,lo,hi,d,k,parent,edge):
        nonlocal generated,peak
        hi=min(hi,horizon)
        if lo>hi or d>budget or k>max_rides:return
        raw_hi=hi
        if node in waitable and node!=target:hi=horizon
        key=node,k; old=seen.setdefault(key,[])
        for a,b in uncovered(lo,hi,[(p.lo,p.hi) for p in old if p.distance<=d]):
            l=Span(node,a,b,d,k,raw_hi,parent,edge)
            old.append(l);heappush(queue,(a,d,k,next(serial),l));generated+=1
        peak=max(peak,len(queue))
    add(source,start,start,0,0,None,None)
    while queue:
        _,_,_,_,l=heappop(queue);expanded+=1
        if l.node==target:
            actions=[];cur=l;tm=l.lo
            while cur.parent is not None:
                # If time lies in the waiting suffix, use the last actual
                # arrival of the original interval and wait at this node.
                arrival=min(tm,cur.raw_hi);e=cur.edge
                if isinstance(e,Walk):
                    depart=arrival-e.duration;actions.append(('walk',e.id,depart,arrival))
                else:
                    depart=e.depart;actions.append(('ride',e.id,depart,e.arrive))
                cur=cur.parent;tm=depart
            return dict(arrival=l.lo,distance=l.distance,rides=l.rides,actions=actions[::-1],expanded=expanded,generated=generated,peak_queue=peak)
        for e in out[l.node]:
            if isinstance(e,Walk):
                for a,b in e.windows:
                    lo=max(a,l.lo);hi=min(l.hi,b-1,b-e.duration)
                    if lo<=hi:add(e.v,lo+e.duration,hi+e.duration,l.distance+e.distance,l.rides,l,e)
            else:
                if l.lo<=e.depart<=l.hi and (l.rides or e.depart<=first_by):
                    add(e.v,e.arrive,e.arrive,l.distance,l.rides+1,l,e)
    return None
