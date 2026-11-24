from cape_s import Model, F, solve as exact, independent_lp
from cape_lazy import solve, verify
from benchmark import random_model
import random,time,json,statistics

def sensors(k,b,perfect=True,seed=71):
    rng=random.Random(seed);n=3
    rows=[]
    if perfect: rows.append(tuple(tuple(F(int(i==j)) for j in range(n)) for i in range(n)))
    else: rows.append(((F(9,10),F(1,10),F(2,10)),(F(1,10),F(9,10),F(8,10))))
    for _ in range(k-1):
        p=tuple(F(rng.randrange(1,20),20) for w in range(n));rows.append((p,tuple(1-x for x in p)))
    priors=tuple(tuple(F(6 if i==j else 2,10) for j in range(n)) for i in range(n))
    return Model(priors,tuple(rows),tuple(tuple(F(int(i==j)) for j in range(n)) for i in range(n)),(1,)*k,(1,)*k,b)

def encode(c):return [dict(expanded=x['expanded'],nodes=x['nodes'],L=str(x['L']),U=str(x['U'])) for x in c['history']]

def main():
    small=[]
    for i in range(60):
        m=random_model(i);e=exact(m);a=solve(m,batch=3);ref,_=independent_lp(m);assert verify(m,a);assert a['L']==a['U']==e['L']==e['U'];assert abs(float(a['L'])-ref)<1e-8
        small.append(dict(seed=i,L=str(a['L']),U=str(a['U']),oracle=ref,exact_nodes=len(e['nodes']),history=encode(a)))
    scale=[]
    for k,b in [(6,3),(8,4),(10,4)]:
        m=sensors(k,b);times={'lazy':[],'exact':[]}
        for i in range(3):
            for name,fn in [('lazy',lambda:solve(m,batch=1)),('exact',lambda:exact(m))][::(-1)**i]:
                t=time.perf_counter();c=fn();times[name].append(time.perf_counter()-t)
                if name=='lazy':a=c;assert verify(m,a)
                else:e=c
        assert a['L']==a['U']==e['L']==e['U']==1
        scale.append(dict(sensors=k,budget=b,exact_nodes=len(e['nodes']),lazy_nodes=a['history'][-1]['nodes'],expanded=a['history'][-1]['expanded'],L=str(a['L']),U=str(a['U']),seconds={k:statistics.median(v) for k,v in times.items()},raw_seconds=times))
    hard=[]
    m=sensors(7,3,False);t=time.perf_counter();e=exact(m);elapsed=time.perf_counter()-t
    for cap in (1,8,32,100,300):
        t=time.perf_counter();a=solve(m,max_expansions=cap,batch=8);dt=time.perf_counter()-t
        assert verify(m,a) and a['L']<=e['L']<=e['U']<=a['U'];hard.append(dict(cap=cap,L=str(a['L']),U=str(a['U']),nodes=a['history'][-1]['nodes'],expanded=a['history'][-1]['expanded'],seconds=dt,history=encode(a)))
    data=dict(small=small,scale=scale,hard=dict(exact_L=str(e['L']),exact_U=str(e['U']),exact_nodes=len(e['nodes']),exact_seconds=elapsed,partial=hard))
    with open('results_lazy.json','w') as f:json.dump(data,f,indent=2)
    print(json.dumps(dict(scale=scale,hard={**data['hard'],'partial':[{k:v for k,v in x.items() if k!='history'} for x in hard]}),indent=2))
if __name__=='__main__':main()
