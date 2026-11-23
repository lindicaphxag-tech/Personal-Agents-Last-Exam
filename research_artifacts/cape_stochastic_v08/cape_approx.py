"""Certified grid information relaxation + executable finite-memory policies."""
from cape_s import Model, F, simplex
from collections import defaultdict
from scipy.optimize import linprog
from scipy.sparse import coo_matrix
import numpy as np


def split(q,K):
    """Exact systematic rounding: sparse convex decomposition on K-grid."""
    c=[F(0)]
    for x in q: c.append(c[-1]+K*x)
    cuts=sorted({F(0),F(1)}|{v-int(v) for v in c})
    out=defaultdict(F)
    for a,b in zip(cuts,cuts[1:]):
        t=(a+b)/2
        floors=[int(v-t) if v>=t else -1 for v in c] # floor(c-t), c>=0
        v=tuple(y-x for x,y in zip(floors,floors[1:]))
        out[v]+=b-a
    assert sum(out.values())==1 and all(sum(v)==K and min(v)>=0 for v in out)
    return tuple(out.items())


def representative(q,K):
    """Nearest by squared distance subject to exact support preservation."""
    v=[max(int(K*x),1) if x else 0 for x in q]
    while sum(v)>K:
        i=min((i for i,x in enumerate(v) if x>1),key=lambda i: -2*(v[i]-K*q[i])+1)
        v[i]-=1
    while sum(v)<K:
        i=min((i for i,x in enumerate(q) if x),key=lambda i: 2*(v[i]-K*q[i])+1)
        v[i]+=1
    return tuple(v)


def compile_grid(m,K,relax=False):
    n=len(m.priors[0]); assert isinstance(K,int) and K>=n and K%n==0
    root=(m.caps,(K//n,)*n,m.budget)
    nodes=[root]; index={root:0}; edges=[]
    for caps,v,b in nodes:
        q=tuple(F(x,K) for x in v); out={}
        for a,rows in enumerate(m.likelihood):
            if not caps[a] or m.costs[a]>b: continue
            c=list(caps); c[a]-=1; out[a]=[]
            for o,row in enumerate(rows):
                raw=tuple(x*F(y) for x,y in zip(q,row)); mass=sum(raw)
                if not mass: continue
                posterior=tuple(x/mass for x in raw)
                children=split(posterior,K) if relax else ((representative(posterior,K),F(1)),)
                for w,alpha in children:
                    t=(tuple(c),w,b-m.costs[a])
                    if t not in index: index[t]=len(nodes);nodes.append(t)
                    out[a].append((o,index[t],mass*alpha))
        edges.append(out)
    return nodes,edges


def candidate(m,K,nodes,edges):
    n=len(m.priors[0]); d=len(m.reward); J=len(m.priors)
    keys=[(s,a) for s,out in enumerate(edges) for a in list(range(-d,0))+list(out)]
    ix={k:i for i,k in enumerate(keys)}; N=len(keys); rr=[];cc=[];vv=[]
    C=np.zeros((J,N+1));C[:,-1]=1
    for i,(s,a) in enumerate(keys):
        rr.append(s);cc.append(i);vv.append(1.)
        if a>=0:
            for _,t,k in edges[s][a]:rr.append(t);cc.append(i);vv.append(-float(k))
        else:
            q=nodes[s][1]
            for j,p in enumerate(m.priors): C[j,i]=-float(n*sum(F(pw)*F(qw,K)*F(v) for pw,qw,v in zip(p,q,m.reward[-a-1])))
    A=coo_matrix((vv,(rr,cc)),shape=(len(nodes),N+1)).tocsr(); b=np.zeros(len(nodes));b[0]=1
    obj=np.zeros(N+1);obj[-1]=-1
    r=linprog(obj,A_ub=C,b_ub=np.zeros(J),A_eq=A,b_eq=b,bounds=[(0,None)]*N+[(None,None)],method='highs')
    if not r.success:raise RuntimeError(r.message)
    policy=[]
    for s,out in enumerate(edges):
        actions=list(range(-d,0))+list(out);policy.append(dict(zip(actions,simplex([r.x[ix[s,a]] for a in actions]))))
    return policy,simplex(-r.ineqlin.marginals)


def replay(m,nodes,edges,policy):
    n=len(m.priors[0]);d=len(m.reward)
    if len(policy)!=len(nodes):raise ValueError('wrong policy size')
    val=[[F(0)]*n for _ in nodes]
    for s in reversed(range(len(nodes))):
        p=policy[s]
        if set(p)!=set(range(-d,0))|set(edges[s]) or min(p.values())<0 or sum(p.values())!=1:raise ValueError('invalid policy')
        for a,pa in p.items():
            if not pa:continue
            if a<0:
                for w,r in enumerate(m.reward[-a-1]):val[s][w]+=pa*F(r)
            else:
                for o,t,_ in edges[s][a]:
                    for w in range(n):val[s][w]+=pa*F(m.likelihood[a][o][w])*val[t][w]
    return min(sum(F(pw)*v for pw,v in zip(p,val[0])) for p in m.priors),tuple(val[0])


def upper(m,K,nodes,edges,y):
    n=len(m.priors[0]);d=len(m.reward)
    if len(y)!=len(m.priors) or min(y)<0 or sum(y)!=1:raise ValueError('invalid dual')
    u=[sum(yj*F(p[w]) for yj,p in zip(y,m.priors)) for w in range(n)]
    V=[F(0)]*len(nodes)
    for s in reversed(range(len(nodes))):
        q=nodes[s][1]
        stop=[n*sum(F(qw,K)*uw*F(rw) for qw,uw,rw in zip(q,u,r)) for r in m.reward]
        V[s]=max(stop+[sum(k*V[t] for _,t,k in children) for children in edges[s].values()])
    return V[0]


def solve(m,K):
    nodes,edges=compile_grid(m,K);p,y=candidate(m,K,nodes,edges)
    L,world=replay(m,nodes,edges,p)
    un,ue=compile_grid(m,K,True);U=upper(m,K,un,ue,y)
    assert L<=U
    return dict(K=K,policy=p,dual=y,L=L,U=U,world=world,lower_nodes=len(nodes),upper_nodes=len(un))


def verify(m,c):
    K=c['K'];nodes,edges=compile_grid(m,K);un,ue=compile_grid(m,K,True)
    L,world=replay(m,nodes,edges,c['policy']);U=upper(m,K,un,ue,c['dual'])
    return L==c['L'] and U==c['U'] and world==c['world'] and L<=U


def anytime(m,grids,tolerance=F(0)):
    records=[];bestL=None;bestU=None
    for K in grids:
        c=solve(m,K);records.append(c)
        if bestL is None or c['L']>bestL['L']:bestL=c
        if bestU is None or c['U']<bestU['U']:bestU=c
        if bestU['U']-bestL['L']<=tolerance:break
    if not records:raise ValueError('empty grid schedule')
    return bestL,bestU,records


def repair(m,K,policy,sweeps=1):
    """Layerwise exact-model policy improvement. Each accepted update is nondecreasing."""
    nodes,edges=compile_grid(m,K); n=len(m.priors[0]); d=len(m.reward); J=len(m.priors)
    layers=defaultdict(list)
    for s,(caps,_,_) in enumerate(nodes): layers[sum(m.caps)-sum(caps)].append(s)
    p=[dict(row) for row in policy]; current,_=replay(m,nodes,edges,p); trace=[current]
    for _ in range(sweeps):
        for layer in sorted(layers,reverse=True):
            active=set(layers[layer]); reach=[[F(0)]*n for s in nodes]; reach[0]=[F(1)]*n; fixed=[F(0)]*n
            # Only paths terminating BEFORE the active layer contribute a constant.
            for s in range(len(nodes)):
                if s in active:continue
                for a,pa in p[s].items():
                    if not pa:continue
                    if a<0:
                        for w in range(n):fixed[w]+=reach[s][w]*pa*F(m.reward[-a-1][w])
                    else:
                        for o,t,_ in edges[s][a]:
                            for w in range(n):reach[t][w]+=reach[s][w]*pa*F(m.likelihood[a][o][w])
            val=[[F(0)]*n for s in nodes]; coeff={}
            for s in reversed(range(len(nodes))):
                for a,pa in p[s].items():
                    v=tuple(map(F,m.reward[-a-1])) if a<0 else tuple(sum(F(m.likelihood[a][o][w])*val[t][w] for o,t,_ in edges[s][a]) for w in range(n))
                    if s in active:coeff[s,a]=[reach[s][w]*v[w] for w in range(n)]
                    if pa:
                        for w in range(n):val[s][w]+=pa*v[w]
            states=[s for s in layers[layer] if any(reach[s])]
            if not states:continue
            keys=[(s,a) for s in states for a in p[s]]; N=len(keys); index={s:i for i,s in enumerate(states)}
            A=coo_matrix(([1.]*N,([index[s] for s,a in keys],list(range(N)))),shape=(len(states),N+1)).tocsr()
            C=np.zeros((J,N+1));C[:,-1]=1
            for i,key in enumerate(keys):
                for j,prior in enumerate(m.priors):C[j,i]=-float(sum(F(pw)*v for pw,v in zip(prior,coeff[key])))
            b=[float(sum(F(pw)*v for pw,v in zip(prior,fixed))) for prior in m.priors]
            obj=np.zeros(N+1);obj[-1]=-1
            res=linprog(obj,A_ub=C,b_ub=b,A_eq=A,b_eq=np.ones(len(states)),bounds=[(0,None)]*N+[(None,None)],method='highs')
            if not res.success:continue
            new=[dict(row) for row in p];i=0
            for s in states:
                k=len(p[s]);new[s]=dict(zip(p[s],simplex(res.x[i:i+k])));i+=k
            L,_=replay(m,nodes,edges,new)
            if L>current:p=new;current=L
            trace.append(current)
    return p,trace


def solve_repaired(m,K,sweeps=1):
    c=solve(m,K); p,trace=repair(m,K,c['policy'],sweeps)
    nodes,edges=compile_grid(m,K);L,world=replay(m,nodes,edges,p)
    # Optimize dual using relaxed problem; upper remains valid for either dual.
    un,ue=compile_grid(m,K,True); _,y=candidate(m,K,un,ue)
    U=upper(m,K,un,ue,y)
    if U>c['U']:U,y=c['U'],c['dual']
    c.update(policy=p,L=L,U=U,world=world,dual=y,repair_trace=trace)
    assert verify(m,c)
    return c
