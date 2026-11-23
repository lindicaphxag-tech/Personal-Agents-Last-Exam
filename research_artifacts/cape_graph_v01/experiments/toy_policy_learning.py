"""Tiny, explicit tabular agent learning experiment over the CAPE evidence plane.

Synthetic *one-step contextual bandit*, NOT an LLM / VLA / large RL model,
not a SOTA comparison, and not an official PALE evaluation. It demonstrates
whether a verified reward changes a learnable policy choice in an environment
where the naive reward has a known invalid high-payoff shortcut.
"""
from __future__ import annotations
from copy import deepcopy
import json
import random
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from capegraph.fixtures import cases, policy
from capegraph.proof_reward import replay_reward
from capegraph.core import digest
from experiments.ablation import outcome_only
from experiments.frontier_evaluation import rubric

ACTIONS=('legitimate','fabricated_witness','duplicated_write','noop')
COST={'legitimate':0.10,'fabricated_witness':0.0,'duplicated_write':0.0,'noop':0.0}


def action_trace(action,domain):
    trusted,effects=deepcopy(cases()[domain])
    if action=='legitimate':pass
    elif action=='fabricated_witness':effects[0]['claims'][0]['witness']='FAKE-SERVICE-RECEIPT'
    elif action=='duplicated_write':
        copy=deepcopy(effects[0]);copy['id']='duplicate_side_effect';copy['idempotency_key']='new-idempotency-key'
        effects.append(copy)
    elif action=='noop':effects=[]
    else:raise ValueError('unknown action')
    return trusted,effects


def reward(action,domain,kind):
    t,e=action_trace(action,domain)
    engine=policy()
    if kind=='naive':
        earned=1.0 if outcome_only(t,e,engine)=='PASS' else 0.0
    elif kind=='certificate':
        proof=replay_reward(engine,rubric(domain),t,e,90,run_id='training:'+domain)
        earned=proof.final_reward
    else:raise ValueError('unknown reward type')
    return round(earned-COST[action],8)


def train(domain,kind,seed,episodes=350):
    rng=random.Random(seed)
    q={a:0.0 for a in ACTIONS}
    visits={a:0 for a in ACTIONS}
    for ep in range(episodes):
        if rng.random()<0.20:
            choice=rng.choice(ACTIONS)
        else:
            high=max(q.values())
            choice=rng.choice([a for a in ACTIONS if abs(q[a]-high)<1e-12])
        value=reward(choice,domain,kind)
        visits[choice]+=1
        q[choice]+=0.22*(value-q[choice])
    top=max(q.values())
    greedy=sorted([a for a in ACTIONS if abs(q[a]-top)<1e-8])[0]
    t,e=action_trace(greedy,domain)
    audit=policy().evaluate(t,e)
    return dict(domain=domain,reward_source=kind,seed=seed,episodes=episodes,
                chosen=greedy,chosen_q=round(q[greedy],6),
                achieved_full_task=audit.verdict=='PASS' and bool(e),
                oracle_verdict=audit.verdict,visits=visits)


def run():
    rows=[train(d,kind,seed) for d in sorted(cases())
          for kind in ('naive','certificate') for seed in range(10)]
    stats={}
    for kind in ('naive','certificate'):
        q=[x for x in rows if x['reward_source']==kind]
        stats[kind]=dict(learned_policies=len(q),verified_completions=sum(x['achieved_full_task'] for x in q),
                         invalid_or_unfinished_policies=sum(not x['achieved_full_task'] for x in q),
                         by_action={a:sum(x['chosen']==a for x in q) for a in ACTIONS})
    return dict(experiment='synthetic one-step contextual bandit proof-of-concept (NOT RL SOTA)',
                domains=3,seeds_per_domain=10,episodes=350,stats=stats,rows=rows)


if __name__=='__main__':
    r=run();r['sha256_without_digest']=digest(r)
    Path(__file__).with_name('toy_policy_learning_results.json').write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({k:v for k,v in r.items() if k!='rows'},indent=2))
