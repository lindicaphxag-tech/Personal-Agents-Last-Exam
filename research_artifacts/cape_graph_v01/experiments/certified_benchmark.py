"""Frozen synthetic evaluation; independently compare complete policy LP and fixed-query LP."""
import sys, json, random, time
from pathlib import Path
from fractions import Fraction as F
from itertools import combinations
from statistics import median
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from capegraph.adaptive import World,Probe,_setup
from capegraph.planner import Goal,Need,Witness,_grade
from capegraph.robust import Prior,_enumerate,_metrics,solve_robust
from capegraph.certified import solve_certified,verify_certificate,solve_flow,verify_flow
from experiments.robust_benchmark import random_case
from capegraph.core import digest

def matrix_lp(rows):
    # Independent LP construction using all rows, no pricing or rationalization.
    import numpy as np
    from scipy.optimize import linprog
    a=np.array(rows,dtype=float); n,m=a.shape
    r=linprog([0.]*n+[-1.],A_ub=np.column_stack((-a.T,np.ones(m))),b_ub=np.zeros(m),A_eq=[[1.]*n+[0.]],b_eq=[1.],bounds=[(0,None)]*n+[(None,None)],method='highs')
    if not r.success:raise RuntimeError(r.message)
    return float(r.x[-1])

def extend(seed):
    gs,qs,ws,b,_=random_case(seed)
    rng=random.Random(seed+991); ps=[]
    if seed%2==0:
        for k,w in enumerate(ws):
            ps.append(Prior('point'+str(k),{z.name:F(z==w) for z in ws}))
    for k in range(3):
        mass=[rng.randrange(1,20) for _ in ws];ps.append(Prior('mix'+str(k),{w.name:F(a,sum(mass)) for w,a in zip(ws,mass)}))
    return gs,qs,ws,b,tuple(ps)

def branch_case(n, qcount=8):
    assert 2<=n<=12 and 2<=qcount<=8
    g=(Goal('validated',(Need('proof','ok',('service',),0,100),),10),)
    probes=(Probe('identify',1,'service'),)+tuple(Probe(f'proof{k:02d}',2,'service') for k in range(qcount))
    worlds=[]
    for i in range(n):
        for j in (0,1):
            winning=(i+j)%qcount
            responses={'identify':(Witness('group',i,'service',1),)}
            responses.update({f'proof{k:02d}':(Witness('proof','ok','service',2),) if k==winning else () for k in range(qcount)})
            worlds.append(World(f'g{i:02d}b{j}',F(1,2*n),responses))
    ps=tuple(Prior(f's{i:02d}',{w.name:F(k==i) for k,w in enumerate(worlds)}) for i in range(len(worlds)))
    return g,probes,tuple(worlds),3,ps

def fixed_mixed(problem):
    gs,qs,ws,b,ps=problem;rows=[]
    for n in range(len(qs)+1):
        for subset in combinations(qs,n):
            if sum(q.cost for q in subset)>b:continue
            vals=[_grade(gs,tuple(r for q in subset for r in w.responses[q.name]))[0] for w in ws]
            rows.append([sum(p.probabilities[w.name]*v for w,v in zip(ws,vals)) for p in ps])
    return matrix_lp(rows)

def run():
    rows=[];times=[]
    for k in range(120):
        prob=extend(2026112500+k);gs,qs,ws,b,ps=prob
        t=time.perf_counter(); r=solve_certified(*prob);dt=time.perf_counter()-t
        t=time.perf_counter();g,q,w,ini=_setup(gs,qs,ws,b,());cs,_=_enumerate(g,q,w,ini,b,prune=True)
        pay=[tuple(v for _,v in _metrics(c,w,ps)[2]) for c in cs]; ref=matrix_lp(pay);old=time.perf_counter()-t
        assert float(r.lower)-1e-7<=ref<=float(r.upper)+1e-7
        assert r.gap<=F(1,10**7) and verify_certificate(r,*prob)==(r.lower,r.upper)
        f=solve_flow(*prob); assert f.gap<=F(1,10**7) and verify_flow(f,*prob)==(f.lower,f.upper)
        assert float(f.lower)-1e-7<=ref<=float(f.upper)+1e-7
        rows.append(dict(case=k,lower=str(r.lower),upper=str(r.upper),gap=str(r.gap),columns=r.generated_columns,frontier=len(cs),nodes=r.dag_nodes,iterations=r.iterations,reference=round(ref,10),flow_lower=str(f.lower),flow_upper=str(f.upper),flow_variables=f.lp_variables))
        times.append((dt,old))
    stress=[]
    for n in (2,3,4,6,8,12):
        prob=branch_case(n,min(n,8));t=time.perf_counter();r=solve_certified(*prob);dt=time.perf_counter()-t
        assert r.lower==r.upper==5
        start=time.perf_counter(); f=solve_flow(*prob); ft=time.perf_counter()-start
        assert f.lower==f.upper==5 and verify_flow(f,*prob)==(5,5)
        assert verify_certificate(r,*prob)==(r.lower,r.upper)
        fixed=fixed_mixed(prob);assert abs(fixed-10/min(n,8))<1e-7
        stress.append(dict(groups=n,worlds=2*n,priors=2*n,queries=len(prob[1]),lower=str(r.lower),upper=str(r.upper),fixed_mixture=fixed,deterministic_upper=0,columns=r.generated_columns,nodes=r.dag_nodes,iterations=r.iterations,distinct_maximal_tag_policies=2**n,flow_variables=f.lp_variables,flow_gap=str(f.gap)))
        print('stress',n,'worlds',2*n,'fixed',fixed,'adaptive',r.lower,'columns',r.generated_columns,'nodes',r.dag_nodes,'seconds',round(dt,4),'flow_seconds',round(ft,4),flush=True)
    obj=dict(scope='synthetic deterministic-receipt finite-world tests; no real agent or service deployment',small_cases=120,certified_cases=len(rows),zero_gap_cases=sum(x['gap']=='0' for x in rows),flow_zero_gap_cases=sum(x['flow_lower']==x['flow_upper'] for x in rows),max_gap=str(max(F(x['gap']) for x in rows)),small_cases_max_frontier=max(x['frontier'] for x in rows),small_cases_max_generated=max(x['columns'] for x in rows),small_cases_total_frontier=sum(x['frontier'] for x in rows),small_cases_total_generated=sum(x['columns'] for x in rows),stress=stress,rows=rows)
    obj['sha256_without_digest']=digest(obj)
    Path(__file__).with_name('certified_results.json').write_text(json.dumps(obj,indent=2)+'\n')
    print('SUMMARY',json.dumps({k:v for k,v in obj.items() if k!='rows'}));print('TIMING median_seconds_new_vs_complete_lp',median(t[0] for t in times),median(t[1] for t in times))
if __name__=='__main__':run()
