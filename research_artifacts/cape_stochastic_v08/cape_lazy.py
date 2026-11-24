"""Anytime restricted-flow / optimistic-fringe certification (static rational model)."""
from fractions import Fraction as F
from collections import defaultdict
from functools import lru_cache
from itertools import combinations
from cape_s import ray, simplex
from scipy.sparse import coo_matrix
from scipy.optimize import linprog
import numpy as np


def root(m): return (m.caps,(1,)*len(m.priors[0]),m.budget)

def belief(s): return tuple(F(x,sum(s[1])) for x in s[1])

def depth(m,s): return sum(m.caps)-sum(s[0])

def actions(m,s):
    caps,_,b=s; q=belief(s); out={}
    for a,rows in enumerate(m.likelihood):
        if not caps[a] or m.costs[a]>b: continue
        c=list(caps);c[a]-=1;children=[]
        for o,row in enumerate(rows):
            v=tuple(x*F(y) for x,y in zip(q,row)); k=sum(v)
            if k:children.append((o,(tuple(c),ray(v),b-m.costs[a]),k))
        out[a]=children
    return out


def compile_partial(m,expanded):
    """Expanded nodes expose every legal query; frontier nodes permit stopping only."""
    r=root(m); nodes={r}; edges={}; queue=[r]
    for s in queue:
        edges[s]=actions(m,s) if s in expanded else {}
        for children in edges[s].values():
            for _,t,_ in children:
                if t not in nodes:nodes.add(t);queue.append(t)
    if not set(expanded)<=nodes:raise ValueError('unreachable expanded state')
    return sorted(nodes,key=lambda s:(depth(m,s),s)),edges


def restricted(m,nodes,edges):
    n=len(m.priors[0]);d=len(m.reward);J=len(m.priors);index={s:i for i,s in enumerate(nodes)}
    keys=[(s,a) for s in nodes for a in list(range(-d,0))+list(edges[s])];N=len(keys)
    rr=[];cc=[];vv=[];C=np.zeros((J,N+1));C[:,-1]=1
    for i,(s,a) in enumerate(keys):
        rr.append(index[s]);cc.append(i);vv.append(1.)
        if a>=0:
            for _,t,k in edges[s][a]:rr.append(index[t]);cc.append(i);vv.append(-float(k))
        else:
            q=belief(s)
            for j,p in enumerate(m.priors):C[j,i]=-float(n*sum(F(pw)*qw*F(v) for pw,qw,v in zip(p,q,m.reward[-a-1])))
    A=coo_matrix((vv,(rr,cc)),shape=(len(nodes),N+1)).tocsr();b=np.zeros(len(nodes));b[0]=1
    obj=np.zeros(N+1);obj[-1]=-1
    r=linprog(obj,A_ub=C,b_ub=np.zeros(J),A_eq=A,b_eq=b,bounds=[(0,None)]*N+[(None,None)],method='highs')
    if not r.success:raise RuntimeError(r.message)
    p={};i=0
    for s in nodes:
        aa=list(range(-d,0))+list(edges[s]);p[s]=dict(zip(aa,simplex(r.x[i:i+len(aa)])));i+=len(aa)
    return p,simplex(-r.ineqlin.marginals)


def replay(m,nodes,edges,policy):
    n=len(m.priors[0]);d=len(m.reward);v={}
    if set(policy)!=set(nodes):raise ValueError('invalid policy nodes')
    for s in reversed(nodes):
        p=policy[s]
        if set(p)!=set(range(-d,0))|set(edges[s]) or any(x<0 for x in p.values()) or sum(p.values())!=1:raise ValueError('invalid policy')
        out=[F(0)]*n
        for a,pa in p.items():
            if not pa:continue
            if a<0:
                for w in range(n):out[w]+=pa*F(m.reward[-a-1][w])
            else:
                for o,t,_ in edges[s][a]:
                    for w in range(n):out[w]+=pa*F(m.likelihood[a][o][w])*v[t][w]
        v[s]=tuple(out)
    return min(sum(F(pw)*r for pw,r in zip(p,v[root(m)])) for p in m.priors)


def pair_oracle(m):
    """Disjoint pair unavoidable-regret bound under adaptive, budgeted observations."""
    n=len(m.priors[0]);pairs=list(combinations(range(n),2))
    best=[max(F(rr[w]) for rr in m.reward) for w in range(n)]
    overlap={(i,j):tuple(sum(min(F(row[i]),F(row[j])) for row in rows) for rows in m.likelihood) for i,j in pairs}
    penalty={(i,j):min(best[i]-F(rr[i])+best[j]-F(rr[j]) for rr in m.reward) for i,j in pairs}
    @lru_cache(None)
    def common(i,j,caps,b):
        value=F(1)
        for a,c in enumerate(caps):
            if c and m.costs[a]<=b:
                nxt=list(caps);nxt[a]-=1
                value=min(value,overlap[i,j][a]*common(i,j,tuple(nxt),b-m.costs[a]))
        return value
    def bound(s,weights):
        clair=sum(w*r for w,r in zip(weights,best));edges=[]
        for i,j in pairs:
            if weights[i] and weights[j] and penalty[i,j]:
                edges.append((min(weights[i],weights[j])*penalty[i,j]*common(i,j,s[0],s[2]),i,j))
        # Any disjoint matching is valid; greedy selection is not claimed optimal.
        used=set();regret=F(0)
        for v,i,j in sorted(edges,reverse=True):
            if i not in used and j not in used:used.update((i,j));regret+=v
        return clair-regret
    return bound


def upper(m,nodes,edges,expanded,y,mode="pair"):
    """Exact optimistic frontier DP; priorities use optimistic-policy reach mass."""
    n=len(m.priors[0]);d=len(m.reward)
    if len(y)!=len(m.priors) or min(y)<0 or sum(y)!=1:raise ValueError('invalid dual')
    u=[sum(yj*F(p[w]) for yj,p in zip(y,m.priors)) for w in range(n)]
    V={};choice={};gaps={};pair_bound=pair_oracle(m) if mode=="pair" else None
    if mode not in ("pair","clair"):raise ValueError("invalid upper mode")
    for s in reversed(nodes):
        q=belief(s);weights=[n*qw*uw for qw,uw in zip(q,u)]
        stop=max(sum(w*F(r) for w,r in zip(weights,rr)) for rr in m.reward)
        opts=[(stop,-1)]
        if s in expanded:
            opts.extend((sum(k*V[t] for _,t,k in children),a) for a,children in edges[s].items())
        elif any(c and cost<=s[2] for c,cost in zip(s[0],m.costs)):
            clair=sum(w*max(F(rr[i]) for rr in m.reward) for i,w in enumerate(weights))
            if pair_bound is not None:clair=pair_bound(s,weights)
            if clair>stop:gaps[s]=clair-stop;opts.append((clair,-2))
        V[s],choice[s]=max(opts,key=lambda x:(x[0],x[1]))
    reach=defaultdict(F);reach[root(m)]=F(1)
    for s in nodes:
        if choice[s]>=0:
            for _,t,k in edges[s][choice[s]]:reach[t]+=reach[s]*k
    ranked=sorted(gaps,key=lambda s:(reach[s]*gaps[s],gaps[s],s),reverse=True)
    return V[root(m)],ranked


def solve(m,max_expansions=100,batch=8,tolerance=F(0),mode="pair"):
    if max_expansions<0 or batch<1 or tolerance<0:raise ValueError('bad limits')
    expanded=set();bestL=None;bestU=None;history=[]
    while True:
        nodes,edges=compile_partial(m,expanded);p,y=restricted(m,nodes,edges)
        L=replay(m,nodes,edges,p);U,rank=upper(m,nodes,edges,expanded,y,mode)
        if bestL is None or L>bestL['L']:bestL=dict(expanded=frozenset(expanded),policy=p,L=L)
        if bestU is None or U<bestU['U']:bestU=dict(expanded=frozenset(expanded),dual=y,U=U,mode=mode)
        history.append(dict(expanded=len(expanded),nodes=len(nodes),L=bestL['L'],U=bestU['U']))
        if bestU['U']-bestL['L']<=tolerance or len(expanded)>=max_expansions:break
        if not rank:break
        expanded.update(rank[:min(batch,max_expansions-len(expanded))])
    return dict(lower=bestL,upper=bestU,history=history,L=bestL['L'],U=bestU['U'])


def verify(m,c):
    try:
        l,u=c['lower'],c['upper'];ln,le=compile_partial(m,l['expanded']);un,ue=compile_partial(m,u['expanded'])
        L=replay(m,ln,le,l['policy']);U,_=upper(m,un,ue,u['expanded'],u['dual'],u['mode'])
        return L==l['L']==c['L'] and U==u['U']==c['U'] and L<=U
    except (ValueError,KeyError,TypeError,IndexError,ZeroDivisionError):return False
