"""Observation-only execution of verified finite-memory policies."""
from cape_approx import compile_grid, verify
from math import lcm
from secrets import randbelow as secure_randbelow

def execute_grid(m,certificate,observe,randbelow=secure_randbelow):
    if not verify(m,certificate):raise ValueError('invalid certificate')
    nodes,edges=compile_grid(m,certificate['K']); s=0; trace=[]
    while True:
        p=certificate['policy'][s]; den=lcm(*(x.denominator for x in p.values()));u=randbelow(den)
        if not isinstance(u,int) or not 0<=u<den:raise ValueError('invalid randomness')
        for a,weight in p.items():
            u-=int(weight*den)
            if u<0:break
        if a<0:return dict(status='DECIDED',decision=-a-1,trace=trace)
        try:o=observe(a)
        except Exception:return dict(status='UNVERIFIED',decision=None,trace=trace)
        if type(o) is not int:return dict(status='UNVERIFIED',decision=None,trace=trace)
        t=next((t for oi,t,_ in edges[s][a] if oi==o),None)
        if t is None:return dict(status='UNVERIFIED',decision=None,trace=trace)
        trace.append((a,o));s=t
