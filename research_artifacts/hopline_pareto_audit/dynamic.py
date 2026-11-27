"""Exact certificate reuse across monotone temporal network restrictions.

Fixed target, deadline, budgets, waiting permissions and trust policy.
Updates remove rides or subtract half-open intervals from walking availability;
no new edges, relaxed windows, or changed costs. The original index stays intact.
"""
from dataclasses import replace
from deadline_fast import build_fast
from joint import prepare, solve_prepared
from temporal import Walk, Ride


def union(spans):
    out=[]
    for a,b in sorted(spans):
        if a>b:continue
        if out and a<=out[-1][1]+1:out[-1]=(out[-1][0],max(b,out[-1][1]))
        else:out.append((a,b))
    return tuple(out)


def cut_windows(windows,cuts):
    """Do not merge original availability windows: traversal must fit one."""
    out=[]
    for a,b in windows:
        spans=[(a,b)]
        for l,h in cuts:
            nxt=[]
            for x,y in spans:
                if h<=x or l>=y:nxt.append((x,y))
                else:
                    if x<l:nxt.append((x,l))
                    if h<y:nxt.append((h,y))
            spans=nxt
        out.extend(spans)
    return tuple(out)


class Base:
    def __init__(self,walks,rides,target,start,deadline,budget,max_rides,first_by,waitable,*,step_free=True,allow_estimates=False):
        self.walks,self.rides=tuple(walks),tuple(rides)
        self.waitable=frozenset(waitable)
        self.step_free,self.allow_estimates=step_free,allow_estimates
        self.index=build_fast(self.walks,self.rides,target,start,deadline,budget,max_rides,first_by,self.waitable,step_free=step_free,allow_estimates=allow_estimates)
        self.edges={e.id:e for e in (*self.walks,*self.rides)}
    def restrict(self,cuts=None,removed=()):
        return Restricted(self,cuts or {},removed)


class Restricted:
    def __init__(self,base,cuts,removed):
        self.base=base;self.idx=base.index;self.removed=frozenset(removed)
        if not self.removed<=base.edges.keys():raise ValueError('unknown removed edge')
        cuts={k:tuple(v) for k,v in cuts.items()}
        if any(k not in base.edges or not isinstance(base.edges[k],Walk) for k in cuts):raise ValueError('cuts require known walking edge')
        if any(type(a) is not int or type(b) is not int or a>=b for ws in cuts.values() for a,b in ws):raise ValueError('invalid closure')
        self.walks=tuple(replace(e,windows=cut_windows(e.windows,cuts[e.id])) if e.id in cuts else e for e in base.walks if e.id not in self.removed)
        self.rides=tuple(e for e in base.rides if e.id not in self.removed)
        self.edges={e.id:e for e in (*self.walks,*self.rides)}
        self.changed=frozenset(k for k,v in base.edges.items() if self.edges.get(k)!=v)
        self.nodes={self.idx.target}|{v for e in (*self.walks,*self.rides) for v in (e.u,e.v)}
        self.waitable=base.waitable & self.nodes
        self.memo={};self.profile=None
        self.stats=dict(old_infeasible=0,reused=0,fallback=0,labels_checked=0,fixed_reused=0,retimed_reused=0)
    def _label(self,l):
        """Return (valid entry-time intervals, feasible immediate departures).

        Evaluate only the immutable tail chain required by a queried label.
        The tail's valid interval—not merely its old witness timestamp—is used.
        """
        chain=[];p=l
        while p is not None and id(p) not in self.memo:chain.append(p);p=p.tail
        for p in reversed(chain):
            self.stats['labels_checked']+=1
            if p.tail is None:
                self.memo[id(p)]=(((p.lo,p.hi),),());continue
            suffix,_=self.memo[id(p.tail)];e=self.edges.get(p.edge.id);dep=[]
            if isinstance(e,Walk):
                for a,b in e.windows:
                    for x,y in suffix:
                        dep.append((max(a,x-e.duration,self.idx.start),min(b-1,b-e.duration,y-e.duration,self.idx.deadline)))
            elif isinstance(e,Ride) and any(a<=e.arrive<=b for a,b in suffix):
                dep.append((e.depart,e.depart))
            dep=union(dep)
            if dep and p.node in self.waitable:valid=union([(p.lo,min(p.hi,dep[-1][1]))])
            else:valid=union((max(p.lo,a),min(p.hi,b)) for a,b in dep)
            self.memo[id(p)]=(valid,dep)
        return self.memo[id(l)]
    def _witness(self,l,tm):
        d,k=l.distance,l.rides;actions=[]
        while l.tail is not None:
            _,dep=self._label(l)
            a=next(max(a,tm) for a,b in dep if max(a,tm)<=b)
            e=self.edges[l.edge.id];b=a+e.duration if isinstance(e,Walk) else e.arrive
            actions.append(('walk' if isinstance(e,Walk) else 'ride',e.id,a,b));tm=b;l=l.tail
        return dict(arrival=tm,distance=d,rides=k,actions=actions)
    def query(self,source,time,budget,max_rides=None):
        i=self.idx;k=i.max_rides if max_rides is None else max_rides
        if any(type(x) is not int for x in (time,budget,k)) or not i.start<=time<=i.deadline or not 0<=budget<=i.budget or not 0<=k<=i.max_rides:raise ValueError('query outside index envelope')
        old=i.query(source,time,budget,k)
        if old is None:
            self.stats['old_infeasible']+=1;return None
        # Most closures do not touch this witness. Replaying only changed
        # edges preserves its exact old optimum with no interval recomputation.
        valid=True
        for kind,eid,a,b in old['actions']:
            if eid not in self.changed:continue
            e=self.edges.get(eid)
            if e is None or isinstance(e,Walk) and not any(x<=a<y and b<=y for x,y in e.windows):valid=False;break
        if valid:
            self.stats['reused']+=1;self.stats['fixed_reused']+=1;return old
        opt=(old['distance'],old['rides'])
        for l in i.labels.get((source,0),()):
            if not l.lo<=time<=l.hi or (l.distance,l.rides)!=opt:continue
            valid,_=self._label(l)
            if any(a<=time<=b for a,b in valid):
                self.stats['reused']+=1;self.stats['retimed_reused']+=1;return self._witness(l,time)
        self.stats['fallback']+=1
        if self.profile is None:
            self.profile=prepare(self.walks,self.rides,i.target,i.budget,i.max_rides,i.deadline-i.start,step_free=self.base.step_free,allow_estimates=self.base.allow_estimates,build_joint=False)
        return solve_prepared(self.profile,source,time,i.deadline,budget,k,i.first_by,self.waitable,joint=False,min_distance=True)
