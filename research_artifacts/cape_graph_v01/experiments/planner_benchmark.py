"""Predeclared CPU-only budgeted evidence-planning experiments.

This measures algorithm correctness on fully synthetic typed query contracts,
not agent success, official PALE difficulty, or empirical trustworthiness.
The exhaustive brute-force comparison is an INDEPENDENT implementation.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from capegraph.core import digest
from capegraph.planner import Need, Goal, Witness, Query, solve_exact, greedy_marginal, brute_force_oracle

SEED_START=20270201
HELDOUT_CASES=360


def fixture_names():
    return {
        "release": ["release:publication", "release:signature", "release:credit", "release:authority"],
        "cpu_lab": ["experiment:holdout", "experiment:cpu-receipt", "experiment:gpu-absent", "experiment:authority"],
        "delivery": ["item:consent", "item:stepfree-route", "item:delivery", "item:authority"],
    }


def constructed_synergy(domain: str):
    keys=fixture_names()[domain]
    goals=(Goal('end_to_end', tuple(Need(k, 'yes', ('service',),0,100) for k in keys), 12),
           Goal('tempting_subgoal', (Need(f'{domain}:decoy','yes',('service',),0,100),), 3))
    qs=tuple(Query(f'fetch-{i}',1,'service',(Witness(k,'yes','service',10+i),)) for i,k in enumerate(keys))
    qs+=(Query('decoy',1,'service',(Witness(f'{domain}:decoy','yes','service',11),)),)
    return goals,qs,4,()


def seeded_world(seed: int):
    rng=random.Random(seed)
    base=seed%3
    prefix=('release','lab','delivery')[base]
    count=rng.randint(3,8)
    tokens=[f'{prefix}:state:{j}' for j in range(count)]
    goals=[]
    for i in range(rng.randint(2,6)):
        chosen=rng.sample(tokens,rng.randint(1,min(4,count)))
        goals.append(Goal(f'{prefix}:goal{i}',tuple(Need(tok,'approved',('service','auditor'),20,80)
               for tok in chosen),rng.randint(2,15)))
    queries=[]
    for j in range(rng.randint(3,10)):
        channel=rng.choice(['service','auditor','outsider'])
        delivered=rng.sample(tokens,rng.randint(1,min(4,count)))
        receipts=tuple(Witness(tok,rng.choice(['approved','approved','denied']),channel,
                               rng.randint(15,90)) for tok in delivered)
        queries.append(Query(f'query{j:02d}',rng.randint(1,5),channel,receipts))
    budget=rng.randint(0,12)
    # Initial records are authenticated by a trusted adapter in this synthetic setup.
    initial=tuple(Witness(tok,rng.choice(['approved','denied']),'service',rng.randint(15,80))
                  for tok in rng.sample(tokens,rng.randint(0,2)))
    return tuple(goals),tuple(queries),budget,initial


def compare(name,scenario,oracle=True):
    goals,queries,budget,initial=scenario
    exact=solve_exact(goals,queries,budget,initial)
    greedy=greedy_marginal(goals,queries,budget,initial)
    if oracle:
        brute=brute_force_oracle(goals,queries,budget,initial)
        assert (exact.value,exact.cost,exact.selected)==(brute.value,brute.cost,brute.selected), name
    assert exact.value>=greedy.value
    return dict(case=name, budget=budget, candidates=len(queries), goal_count=len(goals),
                exact_value=exact.value, greedy_value=greedy.value,
                exact_cost=exact.cost, greedy_cost=greedy.cost,
                exact_selected=list(exact.selected), greedy_selected=list(greedy.selected),
                exact_leaves=exact.explored_leaves, pruned=exact.pruned_branches,
                exact_optimal=exact.optimal)


def run():
    rows=[]
    for domain in sorted(fixture_names()):
        rows.append(compare('constructed:'+domain,constructed_synergy(domain)))
    for i in range(HELDOUT_CASES):
        rows.append(compare('heldout:'+str(SEED_START+i),seeded_world(SEED_START+i)))
    constructed=[r for r in rows if r['case'].startswith('constructed:')]
    heldout=[r for r in rows if r['case'].startswith('heldout:')]
    total_exact=sum(r['exact_value'] for r in heldout)
    total_greedy=sum(r['greedy_value'] for r in heldout)
    result={
        'experimental_scope':'synthetic CPU query contracts; no model agents, no statistical population sample',
        'method':'budgeted conjunctive evidence planning with issuer, time, value and authority restrictions',
        'generating_seed_start':SEED_START,'heldout_count':HELDOUT_CASES,
        'constructed_cases':len(constructed),'constructed_greedy_suboptimal':sum(r['greedy_value']<r['exact_value'] for r in constructed),
        'all_exact_agree_with_independent_bruteforce':True,
        'heldout_exact_total_goal_value':total_exact,
        'heldout_greedy_total_goal_value':total_greedy,
        'heldout_exact_strictly_better':sum(r['exact_value']>r['greedy_value'] for r in heldout),
        'heldout_equal':sum(r['exact_value']==r['greedy_value'] for r in heldout),
        'heldout_strictly_worse':sum(r['exact_value']<r['greedy_value'] for r in heldout),
        'heldout_exact_branches_pruned':sum(r['pruned'] for r in heldout),
        'heldout_exact_leaves_examined':sum(r['exact_leaves'] for r in heldout),
        'rows':rows,
    }
    result['sha256_without_digest']=digest(result)
    return result


if __name__=='__main__':
    out=run()
    root=Path(__file__).resolve().parent
    (root/'planner_results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print({k:v for k,v in out.items() if k not in {'rows','sha256_without_digest'}})
    print('sha256_without_digest',out['sha256_without_digest'])
