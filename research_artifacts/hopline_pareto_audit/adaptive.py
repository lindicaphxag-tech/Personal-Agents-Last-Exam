"""Deterministic backend dispatch; no approximation of reachability."""
from temporal import solve
from interval import solve_interval
from indexed import solve_indexed

def solve_adaptive(walks,rides,source,target,start,horizon,budget,max_rides,first_by,waitable,*,step_free=True,allow_estimates=False):
    walks,rides=tuple(walks),tuple(rides)
    waitable=set(waitable)
    nodes={source,target}|{x for e in (*walks,*rides) for x in (e.u,e.v)}
    args=(walks,rides,source,target,start,horizon,budget,max_rides,first_by,waitable)
    kw=dict(step_free=step_free,allow_estimates=allow_estimates)
    # Threshold chosen on development fragmentation stress; not a theorem about runtime.
    if nodes<=waitable:
        r=solve(*args,**kw);strategy='all_wait_pareto'
    elif sum(len(e.windows) for e in walks)>=256:
        r=solve_indexed(*args,**kw,hybrid=False);strategy='indexed_interval'
    else:
        r=solve_interval(*args,**kw);strategy='list_interval'
    return None if r is None else {**r,'strategy':strategy}
