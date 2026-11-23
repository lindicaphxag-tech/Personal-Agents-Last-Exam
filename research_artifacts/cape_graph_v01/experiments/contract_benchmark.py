"""CAPE-Contract v0.6: preregistered synthetic development/frozen split.

This uses fictional service-side telemetry and no real agents, confidential
accounts, or benchmark test labels. Frozen split is generated without being
passed to synthesis; intentionally unobservable side effects and issuer shift
make limitations measurable instead of silently claiming perfect detection.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import random
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from capegraph.contracts import (Atom, Trace, synthesize_contract, greedy_contract,
                                 independent_oracle, audit_frozen_split)
from capegraph.core import digest
from capegraph.planner import Need, Witness
from capegraph.fixtures import cases,policy

DOMAIN_SPEC={
 'release': [('published','published','registry'),('signature','verified','signer'),
             ('credit','accepted','ledger'),('permission','granted','owner')],
 'lab': [('protocol','frozen','protocol_ledger'),('cpu','success','scheduler'),
         ('gpu','not_executed','scheduler'),('approval','granted','researcher')],
 'delivery': [('consent','accepted','volunteer_service'),('route','step_free','facilities'),
              ('delivery','confirmed','dispatch'),('permission','granted','coordinator')],
}


def components(domain:str):
    spec=DOMAIN_SPEC[domain]
    # All atom candidates are from this declared task-owned schema; the
    # synthetic gold labels are not used to invent arbitrary search predicates.
    atoms=tuple(Atom(domain+':'+name, Need(domain+':'+name,value,(issuer,),10,100),1)
                for name,value,issuer in spec)
    extras=tuple(Atom(domain+':diag:'+str(k),Need(domain+':diag:'+str(k),'ok',('monitor',),10,100),5)
                 for k in (1,2))
    return atoms,extras


def valid_record(domain, rng, name, issuer_shift=False):
    required,extras=components(domain)
    items=[Witness(atom.need.token,atom.need.expected,
                   'migration_delegate' if issuer_shift and i==0 else atom.need.issuers[0],
                   rng.randint(30,75)) for i,atom in enumerate(required)]
    items.extend(Witness(a.need.token,a.need.expected,a.need.issuers[0],rng.randint(30,75)) for a in extras)
    if rng.random() < 0.4:
        atom=rng.choice(required)
        # Stale prior state before newer valid state is NOT a contradiction.
        current=next(x for x in items if x.token==atom.need.token)
        items.append(Witness(atom.need.token,'old',current.issuer,current.at-1))
    rng.shuffle(items)
    return Trace(name,tuple(items),True)


def corrupt(domain,rng,name,variant,which):
    original=valid_record(domain,rng,'temporary')
    required,_=components(domain)
    atom=required[which]
    evidence=list(original.receipts)
    i=next(i for i,x in enumerate(evidence) if x.token==atom.need.token and x.value==atom.need.expected)
    item=evidence[i]
    if variant=='missing':
        evidence=[x for x in evidence if x.token!=atom.need.token]
    elif variant=='wrong_value':
        evidence[i]=Witness(item.token,'denied',item.issuer,item.at)
    elif variant=='wrong_issuer':
        evidence[i]=Witness(item.token,item.value,'agent_self_report',item.at)
    elif variant=='stale':
        evidence[i]=Witness(item.token,item.value,item.issuer,9)
    elif variant=='superseded':
        evidence.append(Witness(item.token,'revoked',item.issuer,min(item.at+1,99)))
    elif variant=='conflicted':
        evidence.append(Witness(item.token,'revoked',item.issuer,item.at))
    elif variant=='future':
        evidence[i]=Witness(item.token,item.value,item.issuer,110)
    else:
        raise ValueError(variant)
    rng.shuffle(evidence)
    return Trace(name,tuple(evidence),False)


def dataset(domain):
    # Different fixed seeds, and the frozen test split is not inspected in CEGIS.
    rng_dev=random.Random(7131+list(DOMAIN_SPEC).index(domain)*10007)
    rng_test=random.Random(19459+list(DOMAIN_SPEC).index(domain)*10009)
    positives=tuple(valid_record(domain,rng_dev,'dev_good_'+str(i)) for i in range(6))
    negatives=tuple(corrupt(domain,rng_dev,f'dev_bad_{k}_{i}',kind,k)
                    for k in range(4) for i,kind in enumerate(('missing','wrong_value','wrong_issuer','stale','superseded')))
    held_good=tuple(valid_record(domain,rng_test,'held_good_'+str(i)) for i in range(120))
    held_new_source=tuple(valid_record(domain,rng_test,'held_migration_'+str(i),issuer_shift=True) for i in range(15))
    variants=['missing','wrong_value','wrong_issuer','stale','superseded','conflicted','future']
    held_bad=tuple(corrupt(domain,rng_test,'held_bad_'+str(i),variants[i%len(variants)],i%4) for i in range(120))
    # These carry *identical apparently valid evidence*; the invalid outcome is
    # a separately committed unauthorized side effect. No evidence-only rule
    # can distinguish them. Their safety rejection needs the external guard.
    hidden_bad=tuple(Trace('held_unauthorized_effect_'+str(i),
                           valid_record(domain,rng_test,'temp').receipts,False) for i in range(30))
    return positives,negatives,held_good,held_new_source,held_bad,hidden_bad


def guard_effect_failure(domain:str):
    trusted,effects=cases()[domain]
    base=policy().evaluate(trusted,effects).verdict
    changed=deepcopy(effects)
    changed[0]['grant_id']='missing-or-forged-permission'
    unsafe=policy().evaluate(trusted,changed).verdict
    assert base=='PASS' and unsafe=='FAIL', (base,unsafe)
    return {'authorized_effect':base,'unauthorized_effect':unsafe}


def run():
    rows=[]
    for domain in DOMAIN_SPEC:
        pos,neg,held_pos,shift_pos,held_bad,hidden_bad=dataset(domain)
        candidate=(*components(domain)[0],*components(domain)[1])
        result=synthesize_contract(candidate,pos,neg)
        assert result.status=='SEPARATED'
        true_exact=independent_oracle(candidate,pos,neg)
        assert true_exact==result.contract
        greedy=greedy_contract(candidate,pos,neg)
        frozen=audit_frozen_split(result.contract,held_pos+shift_pos,held_bad+hidden_bad)
        # All apparent valid observations in hidden_bad are accepted by the
        # evidence contract, but MUST be refused by a real side-effect audit.
        hidden_raw=sum(result.contract.evaluate(t.receipts)=='PASS' for t in hidden_bad)
        side=guard_effect_failure(domain)
        guarded_false_accept=sum(result.contract.with_effect_audit(t.receipts,side['unauthorized_effect'])=='PASS'
                                 for t in hidden_bad)
        chosen=tuple(a.name for a in result.contract.atoms)
        assert len(chosen)==4 and hidden_raw==30 and guarded_false_accept==0
        assert frozen['valid_withheld']==len(shift_pos) and frozen['invalid_falsely_accepted']==30
        assert frozen['invalid_withheld']==len(held_bad)
        rows.append({'domain':domain,'status':result.status,'selected_atoms':chosen,
                     'optimal_cost':result.contract.total_cost,'greedy_cost':greedy.total_cost,
                     'dev_positives':len(pos),'dev_negatives':len(neg),
                     'cegis_oracle_calls':result.oracle_calls,'cegis_counterexamples':len(result.counterexamples),
                     'exact_independent_oracle':true_exact==result.contract,
                     'frozen':frozen, 'out_of_schema_source_valid_withheld':len(shift_pos),
                     'effect_only_attack_raw_false_accept':hidden_raw,
                     'effect_only_attack_after_guard':guarded_false_accept,
                     'effect_guard_verdicts':side,'certificate_sha256':result.as_dict()['sha256_without_digest']})
    metrics={
      'name':'CAPE-Contract v0.6 finite counterexample-guided evidence synthesis',
      'protocol':'task-owner candidate schema; development-only finite counterexample oracle; independently seeded frozen synthetic split',
      'scope':'All receipts, labels and effect logs are fictional and created for testing; no real task or out-of-distribution guarantee',
      'domains':len(rows),'development_positive_total':sum(x['dev_positives'] for x in rows),
      'development_negative_total':sum(x['dev_negatives'] for x in rows),
      'frozen_valid_total':sum(x['frozen']['valid_count'] for x in rows),
      'frozen_invalid_total':sum(x['frozen']['invalid_count'] for x in rows),
      'frozen_valid_withheld':sum(x['frozen']['valid_withheld'] for x in rows),
      'frozen_invalid_falsely_accepted_by_contract_only':sum(x['frozen']['invalid_falsely_accepted'] for x in rows),
      'effect_only_attacks_blocked_by_independent_guard':sum(x['effect_only_attack_raw_false_accept']-x['effect_only_attack_after_guard'] for x in rows),
      'all_syntheses_match_independent_exact_oracle':all(x['exact_independent_oracle'] for x in rows),
      'rows':rows,
    }
    metrics['sha256_without_digest']=digest(metrics)
    return metrics


if __name__=='__main__':
    data=run()
    out=Path(__file__).with_name('contract_results.json')
    out.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in data.items() if k!='rows'},indent=2))
    for x in data['rows']:
        print(x['domain'],x['selected_atoms'],'development',x['dev_positives'],x['dev_negatives'],
              'frozen',x['frozen'],'oracle calls',x['cegis_oracle_calls'])
