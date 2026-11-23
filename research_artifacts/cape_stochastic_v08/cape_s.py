"""CAPE-S prototype: exact likelihood-quotient planning under static ambiguity."""
from fractions import Fraction as F
from functools import lru_cache
from dataclasses import dataclass
from itertools import product
from math import gcd, lcm
from functools import reduce
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

def simplex(v):
    r=tuple(F(max(0.,float(x))).limit_denominator(10**8) for x in v)
    return tuple(x/sum(r) for x in r) if sum(r) else (F(1),)+(F(0),)*(len(r)-1)

def ray(q):
    den=lcm(*(v.denominator for v in q)); a=tuple(int(v*den) for v in q)
    g=reduce(gcd,a)
    return tuple(v//g for v in a)

@dataclass(frozen=True)
class Model:
    priors: tuple  # J x W, exact rational
    likelihood: tuple # A x O x W, conditionally independent observations
    reward: tuple # D x W, terminal decisions incl. abstention if desired
    caps: tuple # max repetitions per action type
    costs: tuple
    budget: int
    def __post_init__(self):
        n=len(self.priors[0]); a=len(self.likelihood)
        assert n and self.reward and len(self.caps)==len(self.costs)==a
        assert self.budget>=0 and all(isinstance(x,int) and x>=0 for x in self.caps)
        assert all(isinstance(x,int) and x>0 for x in self.costs)
        for p in self.priors: assert len(p)==n and min(p)>=0 and sum(p)==1
        for rows in self.likelihood:
            assert rows and all(len(r)==n and min(r)>=0 for r in rows)
            assert all(sum(r[w] for r in rows)==1 for w in range(n))
        assert all(len(r)==n for r in self.reward)

def graph(m, quotient=True):
    n=len(m.priors[0]); root=(m.caps,(1,)*n,m.budget,())
    nodes=[root]; idx={root:0}; edges=[]
    for caps,r,b,h in nodes:
        q=tuple(F(x,sum(r)) for x in r); out={}
        for a,rows in enumerate(m.likelihood):
            if not caps[a] or m.costs[a]>b: continue
            c=list(caps); c[a]-=1; children=[]
            for o,row in enumerate(rows):
                v=tuple(qw*F(l) for qw,l in zip(q,row)); k=sum(v)
                if not k: continue
                t=(tuple(c),ray(v),b-m.costs[a],() if quotient else h+((a,o),))
                if t not in idx: idx[t]=len(nodes); nodes.append(t)
                children.append((o,idx[t],k))
            out[a]=children
        edges.append(out)
    return nodes,edges

def solve(m, quotient=True):
    nodes,edges=graph(m,quotient); n=len(m.priors[0]); d=len(m.reward); J=len(m.priors)
    keys=[(s,a) for s,out in enumerate(edges) for a in list(range(-d,0))+list(out)]
    ix={k:i for i,k in enumerate(keys)}; N=len(keys); rr=[]; cc=[]; vv=[]
    rewards=np.zeros((J,N+1)); rewards[:,-1]=1
    for i,(s,a) in enumerate(keys):
        rr.append(s);cc.append(i);vv.append(1.)
        if a>=0:
            for _,t,k in edges[s][a]: rr.append(t);cc.append(i);vv.append(-float(k))
        else:
            r=nodes[s][1]; q=[F(x,sum(r)) for x in r]
            for j,p in enumerate(m.priors): rewards[j,i]=-float(n*sum(F(pw)*qw*F(v) for pw,qw,v in zip(p,q,m.reward[-a-1])))
    A=coo_matrix((vv,(rr,cc)),shape=(len(nodes),N+1)).tocsr(); b=np.zeros(len(nodes));b[0]=1
    c=np.zeros(N+1);c[-1]=-1
    res=linprog(c,A_ub=rewards,b_ub=np.zeros(J),A_eq=A,b_eq=b,bounds=[(0,None)]*N+[(None,None)],method='highs')
    if not res.success: raise RuntimeError(res.message)
    policy=[]
    for s,out in enumerate(edges):
        actions=list(range(-d,0))+list(out); weights=simplex([res.x[ix[s,a]] for a in actions]); policy.append(dict(zip(actions,weights)))
    y=simplex(-res.ineqlin.marginals)
    L,U=certify(m,nodes,edges,policy,y)
    return dict(nodes=nodes,edges=edges,policy=policy,dual=y,L=L,U=U,variables=N+1,objective=res.x[-1])

def certify(m,nodes,edges,policy,y):
    """Replay per-world probabilities (lower bound); exact reference DP (upper)."""
    n=len(m.priors[0]); d=len(m.reward); J=len(m.priors)
    assert len(y)==J and min(y)>=0 and sum(y)==1
    assert len(policy)==len(nodes)
    pay=[[F(0) for _ in range(n)] for _ in nodes]
    u=[sum(y[j]*F(m.priors[j][w]) for j in range(J)) for w in range(n)]
    V=[F(0)]*len(nodes)
    for s in reversed(range(len(nodes))):
        p=policy[s]; assert set(p)==set(range(-d,0))|set(edges[s]) and min(p.values())>=0 and sum(p.values())==1
        r=nodes[s][1]; q=[F(x,sum(r)) for x in r]; scores=[]
        for a,pa in p.items():
            if a<0:
                v=m.reward[-a-1]; scores.append(n*sum(qw*uw*F(vw) for qw,uw,vw in zip(q,u,v)))
                for w in range(n): pay[s][w]+=pa*F(v[w])
            else:
                scores.append(sum(k*V[t] for _,t,k in edges[s][a]))
                for o,t,k in edges[s][a]:
                    for w in range(n): pay[s][w]+=pa*F(m.likelihood[a][o][w])*pay[t][w]
        V[s]=max(scores)
    L=min(sum(F(pw)*v for pw,v in zip(p,pay[0])) for p in m.priors)
    assert L<=V[0]
    return L,V[0]

def verify(m,certificate,quotient=True):
    """Recompile graph; do not trust supplied graph or reported bounds."""
    nodes,edges=graph(m,quotient)
    L,U=certify(m,nodes,edges,certificate['policy'],certificate['dual'])
    return L==certificate['L'] and U==certificate['U']

def enumerate_vectors(m):
    """Independent full policy-tree payoff enumeration for tiny budgets."""
    n=len(m.priors[0]);
    @lru_cache(None)
    def rec(caps,b):
        result={tuple(map(F,v)) for v in m.reward}
        for a,rows in enumerate(m.likelihood):
            if not caps[a] or m.costs[a]>b: continue
            c=list(caps);c[a]-=1
            sub=rec(tuple(c),b-m.costs[a])
            for choices in product(sub,repeat=len(rows)):
                result.add(tuple(sum(F(row[w])*v[w] for row,v in zip(rows,choices)) for w in range(n)))
        return result
    return rec(m.caps,m.budget)

def independent_lp(m):
    vectors=list(enumerate_vectors(m)); k=len(vectors)
    A=[[-float(sum(F(pw)*v for pw,v in zip(p,r))) for r in vectors]+[1.] for p in m.priors]
    res=linprog([0.]*k+[-1.],A_ub=A,b_ub=[0.]*len(A),A_eq=[[1.]*k+[0.]],b_eq=[1.],bounds=[(0,None)]*k+[(None,None)],method='highs')
    assert res.success
    return res.x[-1],k

def execute(m,cert,observe,randbelow):
    """Only observations enter the controller; returns terminal decision or None."""
    if not verify(m,cert): raise ValueError('invalid certificate')
    nodes,edges=graph(m); s=0
    while True:
        p=cert['policy'][s]; den=lcm(*(x.denominator for x in p.values())); u=randbelow(den)
        for a,x in p.items():
            u-=int(x*den)
            if u<0: break
        if a<0: return -a-1
        try: o=observe(a)
        except Exception: return None
        t=next((t for k,t,_ in edges[s][a] if k==o),None)
        if t is None: return None
        s=t
