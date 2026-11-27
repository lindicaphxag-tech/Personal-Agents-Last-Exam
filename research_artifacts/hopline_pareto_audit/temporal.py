"""Exact finite-horizon resource routing with explicit waiting and trust policy."""
from dataclasses import dataclass
from heapq import heappush, heappop
from itertools import count

@dataclass(frozen=True)
class Walk:
    id: str
    u: str
    v: str
    duration: int
    distance: int
    windows: tuple[tuple[int,int], ...]
    step_free: bool = True
    estimated: bool = False

@dataclass(frozen=True)
class Ride:
    id: str
    u: str
    v: str
    depart: int
    arrive: int
    step_free: bool = True
    estimated: bool = False

@dataclass(frozen=True)
class Label:
    node: str
    time: int
    distance: int
    rides: int
    parent: 'Label | None' = None
    action: tuple | None = None


def solve(walks, rides, source, target, start, horizon, budget, max_rides,
          first_by, waitable, *, step_free=True, allow_estimates=False, force_time_state=False):
    """Return lexicographically best arrival/distance/rides, or None.

    Discrete integer time, full traversal in a half-open availability window.
    A ride is an already compiled boarding-to-alighting connection. Boarding
    waiting is allowed only at waitable nodes; the first boarding deadline is
    absolute. No claim about upstream timetable or facility semantics.
    """
    nums=(start,horizon,budget,max_rides,first_by)
    if any(type(x) is not int for x in nums) or not 0<=start<=horizon or min(budget,max_rides)<0:
        raise ValueError('invalid bounds')
    walks, rides = tuple(walks), tuple(rides)
    nodes={source,target}|{x for e in (*walks,*rides) for x in (e.u,e.v)}
    waitable=set(waitable)
    if not waitable<=nodes: raise ValueError('unknown wait node')
    if len({e.id for e in (*walks,*rides)})!=len(walks)+len(rides): raise ValueError('duplicate edge identity')
    out={n:[] for n in nodes}
    for e in walks:
        if type(e.duration) is not int or type(e.distance) is not int or min(e.duration,e.distance)<0:
            raise ValueError('invalid walk')
        for a,b in e.windows:
            if type(a) is not int or type(b) is not int or a>=b: raise ValueError('invalid window')
        if (not step_free or e.step_free) and (allow_estimates or not e.estimated): out[e.u].append(e)
    for e in rides:
        if type(e.depart) is not int or type(e.arrive) is not int or e.arrive<e.depart: raise ValueError('invalid ride')
        if (not step_free or e.step_free) and (allow_estimates or not e.estimated): out[e.u].append(e)
    # Only compress time when every node permits waiting. Otherwise use exact
    # time states, as a later arrival can be indispensable at a no-wait node.
    compressed=nodes<=waitable and not force_time_state
    fronts={}; queue=[]; serial=count(); expanded=0
    def add(l):
        if l.distance>budget or l.time>horizon or l.rides>max_rides: return
        k=(l.node,l.rides) if compressed else (l.node,l.rides,l.time)
        old=fronts.get(k,[])
        if any(p.time<=l.time and p.distance<=l.distance for p in old): return
        fronts[k]=[p for p in old if not (l.time<=p.time and l.distance<=p.distance)]+[l]
        heappush(queue,(l.time,l.distance,l.rides,next(serial),k,l))
    add(Label(source,start,0,0))
    while queue:
        _,_,_,_,k,l=heappop(queue)
        if not any(p is l for p in fronts[k]): continue
        expanded+=1
        if l.node==target:
            actions=[]; cur=l
            while cur.parent is not None: actions.append(cur.action);cur=cur.parent
            return dict(arrival=l.time,distance=l.distance,rides=l.rides,actions=actions[::-1],expanded=expanded,compressed=compressed)
        if not compressed and l.node in waitable and l.time<horizon:
            add(Label(l.node,l.time+1,l.distance,l.rides,l,('wait',l.node,l.time,l.time+1)))
        for e in out[l.node]:
            if isinstance(e,Walk):
                if compressed:
                    # Earliest usable departure; later departures can be
                    # simulated by waiting at the next node.
                    times=[max(a,l.time) for a,b in e.windows if max(a,l.time)<b and max(a,l.time)+e.duration<=b]
                    if not times: continue
                    t=min(times)
                else:
                    t=l.time
                    if not any(a<=t<b and t+e.duration<=b for a,b in e.windows): continue
                add(Label(e.v,t+e.duration,l.distance+e.distance,l.rides,l,('walk',e.id,t,t+e.duration)))
            else:
                if e.depart<l.time or (not compressed and e.depart!=l.time): continue
                if l.rides==0 and e.depart>first_by: continue
                add(Label(e.v,e.arrive,l.distance,l.rides+1,l,('ride',e.id,e.depart,e.arrive)))
    return None
