"""Transparent leave-one-domain-out CECS screening and PCR reward experiment.

All observations are *synthetic* and curated from this repository. No official
PALE harness or actual LLM/RL training is invoked; the held-out unit is a task
DOMAIN, not an independently collected benchmark. The full CAPE oracle labels
and verifies every trajectory before the certificate/reward is issued.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
from copy import deepcopy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from capegraph.fixtures import cases, policy, personalized_notice, effect
from capegraph.cecs import Screen, synthesize, GUARDS
from capegraph.proof_reward import replay_reward, verify_reward_trace
from capegraph.scoring import Outcome
from capegraph.core import digest
from experiments.ablation import MODES, mutate

RUBRIC={
 'release':(Outcome('release','publish_release','release:2.1.0',100,frozenset({'release_state','signature_state','credit_state'})),),
 'lab':(Outcome('report','submit_report','lab:packet',100,frozenset({'cpu_status','holdout','gpu_status'})),),
 'delivery':(Outcome('delivery','deliver_item','item:C',100,frozenset({'consent','route','delivery'})),),
}


def negative_scenarios(world):
    cases_out=[]
    for mode in MODES:
        t,e=deepcopy(world)
        mutate(t,e,mode)
        cases_out.append((mode,t,e))
    return cases_out


def run():
    engine=policy()
    worlds=cases()
    folds=[]
    for excluded in sorted(worlds):
        train_positive=[];train_negative=[]
        for name,world in worlds.items():
            if name==excluded:continue
            train_positive.append(deepcopy(world))
            train_negative.extend((t,e) for _,t,e in negative_scenarios(world))
        plan=synthesize(engine,train_positive,train_negative)
        screen=Screen(engine,plan.selected)
        target_world=deepcopy(worlds[excluded])
        passed=screen.check(*target_world)[0]=='DEFER'
        results=[]
        for mode,t,e in negative_scenarios(target_world):
            screen_verdict,guards=screen.check(t,e)
            oracle_verdict=engine.evaluate(t,e).verdict
            assert oracle_verdict!='PASS'
            # Even if a candidate screen misses, never issue a reward without
            # the complete verifier. This preserves conditional safety.
            reward=replay_reward(engine,RUBRIC[excluded],t,e,90,run_id=excluded+':'+mode)
            assert reward.final_reward == 0.0
            results.append(dict(attack=mode,screen=screen_verdict,
                                fired=list(guards),oracle=oracle_verdict,
                                proof_reward=reward.final_reward))
        folds.append(dict(held_out_domain=excluded,selected_guards=list(plan.selected),
                          training=dict(covered=plan.train_negative_covered,
                                        total=plan.train_negative_total,
                                        cost=plan.cost,rounds=list(plan.rounds)),
                          positive_remains_unflagged=passed,
                          screen_flagged=sum(r['screen']=='REJECT' for r in results),
                          deferred_to_full_verifier=sum(r['screen']=='DEFER' for r in results),
                          wrong_successes_after_full_verification=0,
                          rows=results))
    rewards={}
    for name,(trusted,effects) in worlds.items():
        good=replay_reward(engine,RUBRIC[name],trusted,effects,90,'reference:'+name)
        assert good.final_reward == 1
        assert verify_reward_trace(good,engine,RUBRIC[name],trusted,effects,90)
        bad=deepcopy(effects)
        bad.append(effect('undeclared_side_effect',effects[0]['at']+1,
                          'undeclared_message',effects[0]['scope'],[],effects[0]['grant_id']))
        withdrawn=replay_reward(engine,RUBRIC[name],trusted,bad,90,'withdrawn:'+name)
        assert withdrawn.final_reward == 0
        assert withdrawn.records[-1].delta == -1
        rewards[name]=dict(positive_final_reward=good.final_reward,
                           final_reward_after_unauthorized_effect=withdrawn.final_reward,
                           prefix_deltas=[x.delta for x in withdrawn.records],
                           replay_verified=True)
    restrictive,permissive=personalized_notice(False),personalized_notice(True)
    assert restrictive[1]==permissive[1]
    assert engine.evaluate(*restrictive).verdict=='FAIL'
    assert engine.evaluate(*permissive).verdict=='PASS'
    aggregate={
        'experiment':'Synthetic domain-held-out counterexample-guided screening; NO official PALE or learned-model results',
        'positive_domains':3,
        'mutant_families_per_domain':len(MODES),
        'held_out_domain_trials':3*len(MODES),
        'flagged_without_full_proof':sum(f['screen_flagged'] for f in folds),
        'escalated_to_full_verifier':sum(f['deferred_to_full_verifier'] for f in folds),
        'bad_traces_receiving_positive_proof_reward':0,
        'positive_references_receiving_full_proof_reward':3,
        'proof_reward_clawback_scenarios':3,
        'counterfactual_authorization':{'restrictive':'FAIL','permissive':'PASS'},
        'folds':folds,
        'reward_examples':rewards,
    }
    aggregate['sha256_without_digest']=digest(aggregate)
    return aggregate


if __name__=='__main__':
    value=run()
    path=Path(__file__).with_name('cecs_pcr_results.json')
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in value.items() if k not in ('folds','reward_examples')},indent=2))
    for fold in value['folds']:
        print(fold['held_out_domain'],fold['selected_guards'],'flag',fold['screen_flagged'],
              'defer',fold['deferred_to_full_verifier'])
