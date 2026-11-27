"""Bit-parallel reverse coverage; exact for bounded discrete horizons."""
from heapq import heappush,heappop
from itertools import count
from types import MappingProxyType
from deadline import Back,DeadlineIndex,build_deadline
from joint import prepare
from temporal import Walk


def spans(bits,offset):
    """Disjoint inclusive runs of a nonnegative integer bitset."""
    while bits:
        a=(bits&-bits).bit_length()-1
        x=bits>>a
        n=(x^(x+1)).bit_length()-1
        yield offset+a,offset+a+n-1
        bits^=((1<<n)-1)<<a


def build_fast(walks,rides,target,start,deadline,budget,max_rides,first_by,waitable,*,step_free=True,allow_estimates=False,bit_limit=4096):
    if any(type(x) is not int for x in (start,deadline,budget,max_rides,first_by,bit_limit)) or not 0<=start<=deadline or min(budget,max_rides,bit_limit)<0:raise ValueError('invalid limits')
    if deadline-start+1>bit_limit:
        return build_deadline(walks,rides,target,start,deadline,budget,max_rides,first_by,waitable,step_free=step_free,allow_estimates=allow_estimates)
    p=prepare(walks,rides,target,budget,max_rides,deadline-start,step_free=step_free,allow_estimates=allow_estimates,build_joint=False)
    waitable=frozenset(waitable)
    if not waitable<=set(p.out):raise ValueError('unknown wait node')
    incoming={v:[] for v in p.out}
    for es in p.out.values():
        for e in es:incoming[e.v].append(e)
    labels={};covers={};q=[];serial=count();expanded=0
    def push(v,lo,hi,prior,d,r,tail,edge):
        if d>budget or prior+r>max_rides:return
        lo=max(lo,start);hi=min(hi,deadline)
        if lo>hi:return
        raw=lo
        if v in waitable:lo=start
        # Only settled labels are used for pruning. Their distance is no
        # greater than the current popped label's distance by heap order.
        mask=((1<<(hi-lo+1))-1)<<(lo-start)
        if mask & ~covers.get((v,prior,r),0):
            heappush(q,(d,r,next(serial),Back(v,lo,hi,prior,d,r,raw,tail,edge)))
    for k in range(max_rides+1):push(target,start,deadline,k,0,0,None,None)
    while q:
        d,r,_,l=heappop(q);v=l.node;k=l.prior
        mask=((1<<(l.hi-l.lo+1))-1)<<(l.lo-start)
        new=mask & ~covers.get((v,k,r),0)
        if not new:continue
        for cap in range(r,max_rides-k+1):
            key=(v,k,cap);covers[key]=covers.get(key,0)|new
        for a,b in spans(new,start):
            x=Back(v,a,b,k,d,r,l.raw_lo,l.tail,l.edge)
            labels.setdefault((v,k),[]).append(x);expanded+=1
            for e in incoming[v]:
                if isinstance(e,Walk):
                    for u,w in e.windows:
                        push(e.u,max(u,a-e.duration),min(w-1,w-e.duration,b-e.duration),k,d+e.distance,r,x,e)
                elif k>0 and a<=e.arrive<=b and (k>1 or e.depart<=first_by):
                    push(e.u,e.depart,e.depart,k-1,d,r+1,x,e)
    return DeadlineIndex(target,start,deadline,budget,max_rides,first_by,waitable,MappingProxyType({k:tuple(v) for k,v in labels.items()}),expanded)
