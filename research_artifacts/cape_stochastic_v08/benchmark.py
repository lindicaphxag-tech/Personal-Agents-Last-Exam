from cape_s import *
import random, time, json, statistics

def random_model(seed):
    r=random.Random(seed); n=3
    priors=[]
    for _ in range(3):
        p=[r.randrange(0,5) for _ in range(n)];p[0]+=1;priors.append(tuple(F(x,sum(p)) for x in p))
    likelihood=[]
    for _ in range(2):
        p=tuple(F(r.randrange(0,5),4) for _ in range(n));likelihood.append((p,tuple(1-x for x in p)))
    return Model(tuple(priors),tuple(likelihood),tuple(tuple(F(int(i==j)) for j in range(n)) for i in range(n)),(1,1),(1,1),2)

def repeated(b):
    return Model(((F(1),F(0)),(F(0),F(1))),(((F(4,5),F(1,5)),(F(1,5),F(4,5))),),((1,0),(0,1)),(b,),(1,),b)

def main():
    small=[]
    for seed in range(60):
        m=random_model(seed); c=solve(m); oracle,k=independent_lp(m); assert abs(float(c['L'])-oracle)<1e-7 and abs(float(c['U'])-oracle)<1e-7 and verify(m,c)
        small.append(dict(seed=seed,L=str(c['L']),U=str(c['U']),oracle=oracle,vectors=k,nodes=len(c['nodes'])))
    scales=[]
    for b in (3,5,7,9,11):
        m=repeated(b); times={True:[],False:[]}; records={}
        for _ in range(3):
            for quotient in (True,False):
                t=time.perf_counter(); c=solve(m,quotient); times[quotient].append(time.perf_counter()-t)
                assert verify(m,c,quotient); records[quotient]=c
        q,h=records[True],records[False]; assert abs(float(q['L']-h['L']))<1e-7 and q['U']==h['U'];
        scales.append(dict(budget=b,nodes_quotient=len(q['nodes']),nodes_history=len(h['nodes']),variables_quotient=q['variables'],variables_history=h['variables'],L=str(q['L']),U=str(q['U']),history_L=str(h['L']),history_U=str(h['U']),seconds_quotient=statistics.median(times[True]),seconds_history=statistics.median(times[False])))
    data=dict(small=small,exact_zero_gap=sum(x['L']==x['U'] for x in small),scaling=scales)
    with open('results.json','w') as f:json.dump(data,f,indent=2)
    print(json.dumps({k:v for k,v in data.items() if k!='small'},indent=2))
if __name__=='__main__':main()
