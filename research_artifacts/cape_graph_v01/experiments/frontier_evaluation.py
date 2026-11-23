"""CECS + PCR v0.2 controlled experiments with a *preheld-out* attack family.

These are deterministic synthetic research examples. The new attack class was
not part of the original 14 mutation families or the initial rule fit. A
single counterexample is subsequently revealed to the synthesizer, with the
other two domains retained for cross-task transfer checks; that is a measured
in-suite transfer, NOT an estimate of deployed-agent generalization.
"""
from __future__ import annotations
from copy import deepcopy
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from capegraph.fixtures import cases, policy, personalized_notice, effect
from capegraph.cecs import Screen, synthesize
from capegraph.metamorphic import rename_world
from capegraph.proof_reward import replay_reward, verify_reward_trace
from capegraph.scoring import Outcome
from capegraph.core import digest
from experiments.ablation import MODES, mutate, outcome_only


def rubric(name):
    value={
        'release':('published','publish_release','release:2.1.0',frozenset({'release_state','signature_state','credit_state'})),
        'lab':('report','submit_report','lab:packet',frozenset({'cpu_status','holdout','gpu_status'})),
        'delivery':('delivery','deliver_item','item:C',frozenset({'consent','route','delivery'})),
    }[name]
    return [Outcome(value[0],value[1],value[2],100,value[3])]


def detach_authority_issued_fact(name, world):
    t,e=deepcopy(world)
    target={'release':'signed_assets','lab':'cpu_receipt','delivery':'receipt_C'}[name]
    next(x for x in t if x['id']==target)['parents']=[]
    return t,e


def execute():
    engine=policy();worlds=cases()
    train_pos=[deepcopy(x) for x in worlds.values()]
    train_neg=[]
    for name,world in worlds.items():
        for mode in MODES:
            t,e=deepcopy(world);mutate(t,e,mode)
            train_neg.append((t,e))
    initial=synthesize(engine,train_pos,train_neg)
    initial_screen=Screen(engine,initial.selected)
    novel={name:detach_authority_issued_fact(name,world) for name,world in worlds.items()}
    novel_pre={name:initial_screen.check(*x)[0] for name,x in novel.items()}
    assert all(engine.evaluate(*x).verdict=='FAIL' for x in novel.values())
    # Select the lab counterexample only, then check transfer to release/delivery.
    refined=synthesize(engine,train_pos,train_neg+[novel['lab']])
    refined_screen=Screen(engine,refined.selected)
    novel_post={name:refined_screen.check(*x)[0] for name,x in novel.items()}
    false_rejections=0
    positive_count=0
    oracle_pass=0
    for name,world in worlds.items():
        for seed in range(20):
            t,e=rename_world(*world,seed)
            positive_count+=1
            if engine.evaluate(t,e).verdict=='PASS':oracle_pass+=1
            if refined_screen.check(t,e)[0]!='DEFER':false_rejections+=1
    reward_rows=[]
    for name,world in worlds.items():
        t,e=deepcopy(world)
        goals=rubric(name)
        valid=replay_reward(engine,goals,t,e,90,'valid:'+name)
        assert verify_reward_trace(valid,engine,goals,t,e,90)
        bad=deepcopy(e);bad.append(effect('adversarial_message',e[0]['at']+1,
                                         'undeclared_message',e[0]['scope'],[],e[0]['grant_id']))
        withdrawn=replay_reward(engine,goals,t,bad,90,'clawback:'+name)
        unknown=deepcopy(e);unknown[0]['claims'][0]['witness']='missing-service-witness'
        uncertain=replay_reward(engine,goals,t,unknown,90,'unverified:'+name)
        noop=replay_reward(engine,goals,t,[],90,'noop:'+name)
        assert valid.final_reward==1 and withdrawn.final_reward==0 and uncertain.final_reward==0 and noop.final_reward==0
        assert withdrawn.records[-1].delta==-1
        reward_rows.append(dict(task=name,positive=valid.final_reward,
                                illegal_late_effect=withdrawn.final_reward,
                                clawback=withdrawn.records[-1].delta,
                                missing_service_proof=uncertain.final_reward,
                                noop=noop.final_reward,
                                certificate_replays=True))
    return dict(
        title='CAPE-Graph v0.2 controlled CECS+PCR experiment',
        scope='Synthetic fixed tasks and programmer-authored attacks; not model trials or PALE accepted tasks',
        original_attack_families=len(MODES),
        original_negative_cases=len(train_neg),
        initial_cecs=initial.to_json(),
        preheldout_novel_family='detached_issuer_valid_causal_parent',
        novel_attack_before_refinement=novel_pre,
        novel_attack_after_one_refinement=novel_post,
        after_refinement=refined.to_json(),
        heldout_transfer_tasks=['release','delivery'],
        positive_alpha_renaming_count=positive_count,
        oracle_positive_survival=oracle_pass,
        screen_positive_false_rejections=false_rejections,
        proof_reward_examples=reward_rows,
        outcome_only_baseline_false_accepts=sum(outcome_only(*x,engine)=='PASS' for x in train_neg),
        full_verifier_false_accepts=sum(engine.evaluate(*x).verdict=='PASS' for x in train_neg),
    )


if __name__=='__main__':
    r=execute();r['sha256_without_digest']=digest(r)
    target=Path(__file__).with_name('frontier_evaluation_results.json')
    target.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in r.items() if k not in ('proof_reward_examples','initial_cecs','after_refinement')},
                     indent=2,ensure_ascii=False))
