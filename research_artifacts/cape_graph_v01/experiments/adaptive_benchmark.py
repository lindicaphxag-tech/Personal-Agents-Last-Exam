"""CAPE-Adapt reproducible finite-world adaptive-vs-fixed evidence-query comparison.

All world distributions and response models are synthetic; results certify exact
optimization under these models, not calibrated real agent performance.
"""
from __future__ import annotations

from fractions import Fraction as F
from pathlib import Path
import json,random,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from capegraph.adaptive import Probe,World,solve_adaptive,evaluate_fixed,expected_replay,brute_force_adaptive_oracle
from capegraph.planner import Need,Goal,Witness
from capegraph.core import digest

COUNT=240
START=20280401


def need(t):return Need(t,'ok',('official','safety'),1,100)
def receipt(t,ch='official',val='ok',time=40):return Witness(t,val,ch,time)


def designed(domain):
    a=f'{domain}:A';b=f'{domain}:B'
    gs=(Goal('A',(need(a),need(a+':finish')),10),Goal('B',(need(b),need(b+':finish')),10))
    qs=(Probe('which',1,'official'),Probe('finish_A',1,'official'),Probe('finish_B',1,'official'))
    ws=(World('A',F(1,2),{'which':(receipt(a),),'finish_A':(receipt(a+':finish'),),'finish_B':()}),
        World('B',F(1,2),{'which':(receipt(b),),'finish_A':(),'finish_B':(receipt(b+':finish'),)}))
    return gs,qs,ws,2


def random_case(seed):
    rng=random.Random(seed)
    tokens=[f't:{i}' for i in range(rng.randint(3,6))]
    goals=tuple(Goal('g'+str(i),tuple(need(x) for x in rng.sample(tokens,rng.randint(1,min(3,len(tokens))))),rng.randint(3,12)) for i in range(rng.randint(2,5)))
    queries=tuple(Probe('query'+str(i),rng.randint(1,3),rng.choice(('official','safety','outsider'))) for i in range(rng.randint(3,5)))
    prior_weights=[rng.randint(1,9) for _ in range(rng.randint(2,4))];total=sum(prior_weights)
    worlds=[]
    for i,wi in enumerate(prior_weights):
        responses={q.name:tuple(receipt(t,q.channel,rng.choice(['ok','ok','bad']),rng.randint(1,95)) for t in rng.sample(tokens,rng.randint(0,2))) for q in queries}
        worlds.append(World('world'+str(i),F(wi,total),responses))
    return goals,queries,tuple(worlds),rng.randint(0,7)


def row(name,problem):
    gs,qs,ws,b=problem
    adaptive=solve_adaptive(gs,qs,ws,b)
    fixed=evaluate_fixed(gs,qs,ws,b)
    exhaustive=brute_force_adaptive_oracle(gs,qs,ws,b)
    replay=expected_replay(adaptive,ws,qs,gs)
    assert exhaustive==replay==(adaptive.decision.expected_goal_value,adaptive.decision.expected_query_cost)
    assert adaptive.decision.expected_goal_value>=fixed[0]
    return {'case':name,'budget':b,'worlds':len(ws),'probes':len(qs),
            'adaptive_value':str(adaptive.decision.expected_goal_value),
            'fixed_value':str(fixed[0]),
            'adaptive_query_cost':str(adaptive.decision.expected_query_cost),
            'fixed_query_cost':fixed[1],
            'strictly_better':adaptive.decision.expected_goal_value>fixed[0],
            'root_action':adaptive.decision.query,
            'states_visited':adaptive.states_visited,
            'oracle_agreement':True}


def run():
    rows=[row('constructed:'+domain,designed(domain)) for domain in ['release','lab','delivery']]
    rows.extend(row('seed:'+str(seed),random_case(seed)) for seed in range(START,START+COUNT))
    held=rows[3:]
    a=sum((F(x['adaptive_value']) for x in held),F(0));b=sum((F(x['fixed_value']) for x in held),F(0))
    obj={
        'name':'CAPE-Adapt finite-world CPU synthetic evaluation',
        'scope':'models are fictional and prior probabilities are developer-specified, not calibrated in real deployments',
        'latent_world_identity_is_never_seen_by_policy':True,
        'world_seed_start':START,'random_cases':COUNT,
        'constructed_adaptivity_gap_cases':3,
        'independent_oracle_agreement':len(rows),
        'constructed_expected_adaptive_value':'10',
        'constructed_expected_fixed_value':'5',
        'random_strict_adaptive_gain':sum(x['strictly_better'] for x in held),
        'random_equal':sum(not x['strictly_better'] for x in held),
        'random_adaptive_total_value':str(a),
        'random_fixed_total_value':str(b),
        'rows':rows
    }
    obj['sha256_without_digest']=digest(obj)
    return obj


if __name__=='__main__':
    out=run()
    (Path(__file__).resolve().parent/'adaptive_results.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
    print({k:v for k,v in out.items() if k not in ('rows','sha256_without_digest')})
    print('sha256_without_digest',out['sha256_without_digest'])
