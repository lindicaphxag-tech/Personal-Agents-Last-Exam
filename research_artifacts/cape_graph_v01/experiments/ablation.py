"""Controlled, deterministic falsification experiment (not model evaluations)."""
from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from capegraph.fixtures import cases, policy, fact, effect, claim, personalized_notice
from capegraph.core import canonical, digest


def outcome_only(trusted, effects, engine):
    """A deliberately weak, transparent EXISTENCE/EXPECTED-VALUE baseline.

    It checks only required fields in *at least one* matching effect per action;
    it ignores extra effects, sources, permissions, duplicates and chronology.
    This is a toy ablation, not a prior published baseline.
    """
    for e in effects:
        rule=engine.rules.get(e['action'])
        if rule is None:
            continue
        claims={x['predicate']:x['value'] for x in e['claims']}
        if all(claims.get(pred)==value for pred,value in rule.required):
            return 'PASS'
    return 'NOT_PASS'


def mutate(t,e,mode):
    root=e[0];g=next(n for n in t if n['id']==root['grant_id'])
    witness=root['claims'][0]['witness']; f=next(n for n in t if n['id']==witness)
    if mode=='extra_action':
        e.append(effect('smuggle_1',root['at']-1,'undeclared_post',root['scope'],[],root['grant_id']))
    elif mode=='duplicate_effect':
        duplicate=deepcopy(root); duplicate['id']='duplicate_1';duplicate['idempotency_key']='key2';e.append(duplicate)
    elif mode=='expired_grant': g['not_after']=root['at']-1
    elif mode=='unauthorized_issuer':g['issuer']='untrusted_stranger'
    elif mode=='untrusted_proof':f['issuer']='agent'
    elif mode=='wrong_proof':root['claims'][0]['witness']=root['claims'][-1]['witness']
    elif mode=='extra_claim':root['claims'].append(claim('research_coauthor','person:avery','yes',witness))
    elif mode=='missing_claim':root['claims'].pop(0)
    elif mode=='missing_witness':root['claims'][0]['witness']='no_issuer_receipt'
    elif mode=='future_witness':root['at']=f['at']-1
    elif mode=='stale_witness':
        t.append(fact('contrary_1',root['at']-1,f['issuer'],f['subject'],f['predicate'],'revoked'))
    elif mode=='wrong_scope':root['scope']='wrong:object'
    elif mode=='revoke':
        t.append(dict(id='rev1',type='revoke',at=root['at']-1,issuer=g['issuer'],grant_id=g['id']))
    elif mode=='false_claim':root['claims'][0]['value']='fabricated'
    else:raise KeyError(mode)


MODES=("extra_action","duplicate_effect","expired_grant","unauthorized_issuer",
       "untrusted_proof","wrong_proof","extra_claim","missing_claim",
       "missing_witness","future_witness","stale_witness","wrong_scope",
       "revoke","false_claim")


def run():
    engine=policy();rows=[]
    for name,(trusted,effects) in cases().items():
        assert engine.evaluate(trusted,effects).verdict=='PASS'
        for mode in MODES:
            t,e=deepcopy((trusted,effects));mutate(t,e,mode)
            val=engine.evaluate(t,e)
            base=outcome_only(t,e,engine)
            rows.append(dict(case=name,attack=mode,ground_truth='invalid',
                             baseline_accepts=base=='PASS',cape_accepts=val.verdict=='PASS',
                             cape_verdict=val.verdict,
                             reason_codes=sorted({f.code for f in val.findings})))
    assert len(rows)==42
    assert sum(r['cape_accepts'] for r in rows)==0, [x for x in rows if x['cape_accepts']]
    alt={}
    for label,allow in [('restrictive',False),('permissive',True)]:
        t,e=personalized_notice(allow)
        alt[label]=engine.evaluate(t,e).verdict
    assert alt=={'restrictive':'FAIL','permissive':'PASS'}
    result={
        'label':'synthetic author-side deterministic negative controls (NOT model rollouts)',
        'cases':['release','lab','delivery'],
        'positive_references':3,
        'mutated_invalid_cases':len(rows),
        'toy_outcome_only_false_accepts':sum(r['baseline_accepts'] for r in rows),
        'cape_false_accepts':sum(r['cape_accepts'] for r in rows),
        'cape_fails':sum(r['cape_verdict']=='FAIL' for r in rows),
        'cape_unverified':sum(r['cape_verdict']=='UNVERIFIED' for r in rows),
        'counterfactual_authorization':alt,
        'rows':rows,
    }
    result['sha256_without_digest']=digest(result)
    return result


if __name__=='__main__':
    r=run()
    root=Path(__file__).resolve().parent
    (root/'ablation_results.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    print({k:v for k,v in r.items() if k not in ('rows','sha256_without_digest')})
    print('sha256_without_digest',r['sha256_without_digest'])
