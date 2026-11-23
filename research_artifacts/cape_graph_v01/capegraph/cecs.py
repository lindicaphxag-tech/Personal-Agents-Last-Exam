"""CECS: counterexample-guided, cost-aware *rejection screening*.

This is a finite-example prototype, not a sound policy synthesizer over an
unbounded state space. The learned screen can flag suspicious traces for
rejection/review but NEVER certifies task success: an unflagged trace is
DEFERRED to the trusted full CAPE-Graph verifier. Its agreement statistics
are only about the controlled examples supplied to fit/evaluate.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Iterable
from collections import Counter, defaultdict
from .core import Verifier, Rule, TRUSTED_FIELDS, EFFECT_FIELDS, CLAIM_FIELDS, canonical

Trace = tuple[list[dict], list[dict]]


def _identity(e):
    return isinstance(e, dict) and isinstance(e.get('id'), str)


def _schema(t: list[dict], e: list[dict], engine: Verifier) -> bool:
    for rec in t:
        if not isinstance(rec, dict) or rec.get('type') not in TRUSTED_FIELDS:
            return True
        if set(rec) != TRUSTED_FIELDS[rec['type']]:
            return True
    for event in e:
        if not isinstance(event,dict) or set(event) != EFFECT_FIELDS:
            return True
        if not isinstance(event.get('claims'),list):
            return True
        if any(not isinstance(c,dict) or set(c)!=CLAIM_FIELDS for c in event['claims']):
            return True
    return False


def _declaration(t,e,engine):
    return any(isinstance(x,dict) and x.get('action') not in engine.rules for x in e)


def _outcome(t,e,engine):
    for event in e:
        if not isinstance(event,dict):continue
        rule=engine.rules.get(event.get('action'))
        if rule is None:continue
        claims=event.get('claims',[])
        if not isinstance(claims,list):continue
        preds=[x.get('predicate') for x in claims if isinstance(x,dict)]
        if len(preds)!=len(set(preds)) or any(x not in rule.allowed for x in preds):return True
        values={x.get('predicate'):x.get('value') for x in claims if isinstance(x,dict)}
        if any(pred not in values or canonical(values[pred])!=canonical(v) for pred,v in rule.required):return True
    return False


def _authority(t,e,engine):
    grants={x['id']:x for x in t if isinstance(x,dict) and x.get('type')=='grant' and _identity(x)}
    revokes=defaultdict(list)
    for r in t:
        if isinstance(r,dict) and r.get('type')=='revoke':revokes[r.get('grant_id')].append(r)
    for event in e:
        if not isinstance(event,dict):continue
        grant=grants.get(event.get('grant_id'))
        if not grant:return True
        if grant.get('issuer') not in engine.grant_issuers:return True
        if any(grant.get(k)!=event.get(k) for k in ('principal','action','scope')):return True
        if not (isinstance(event.get('at'),int) and grant.get('at',float('inf'))<=event['at']<grant.get('not_after',-1)):
            return True
        if any(r.get('at',float('inf'))<=event['at'] for r in revokes.get(event.get('grant_id'),[])):return True
    return False


def _witness(t,e,engine):
    facts={x.get('id'):x for x in t if isinstance(x,dict) and x.get('type')=='fact'}
    for event in e:
        if not isinstance(event,dict):continue
        rule=engine.rules.get(event.get('action'))
        if not isinstance(event.get('claims'),list):continue
        for claim in event['claims']:
            if not isinstance(claim,dict):continue
            proof=facts.get(claim.get('witness'))
            if proof is None:return True
            if proof.get('issuer') not in engine.fact_issuers.get(claim.get('predicate'),frozenset()):return True
            if any(proof.get(k)!=claim.get(k) for k in ('subject','predicate')):return True
            if canonical(proof.get('value'))!=canonical(claim.get('value')):return True
            if isinstance(event.get('at'),int) and proof.get('at',float('inf'))>event['at']:return True
            if rule and claim.get('predicate') in rule.scope_bound and claim.get('subject')!=event.get('scope'):
                return True
    return False


def _freshness(t,e,engine):
    history=defaultdict(list)
    for fact in t:
        if isinstance(fact,dict) and fact.get('type')=='fact' and fact.get('issuer') in engine.fact_issuers.get(fact.get('predicate'),()):
            history[(fact.get('subject'),fact.get('predicate'))].append(fact)
    for event in e:
        if not isinstance(event,dict) or not isinstance(event.get('at'),int):continue
        for claim in event.get('claims',[]) if isinstance(event.get('claims'),list) else []:
            if not isinstance(claim,dict):continue
            eligible=[x for x in history.get((claim.get('subject'),claim.get('predicate')),[]) if isinstance(x.get('at'),int) and x['at']<=event['at']]
            if not eligible:continue
            latest=max(x['at'] for x in eligible)
            newest=[x for x in eligible if x['at']==latest]
            if len({canonical(x.get('value')) for x in newest})>1:return True
            if claim.get('witness') not in {x.get('id') for x in newest}:return True
    return False


def _uniqueness(t,e,engine):
    ids=Counter(x.get('id') for x in e if isinstance(x,dict))
    if any(v>1 for v in ids.values()):return True
    seen=set(); idem=set()
    for x in e:
        if not isinstance(x,dict):continue
        rule=engine.rules.get(x.get('action'))
        if rule and rule.unique:
            key=(x.get('action'),x.get('scope'))
            if key in seen:return True
            seen.add(key)
        key=(x.get('action'),x.get('idempotency_key'))
        if x.get('idempotency_key') and key in idem:return True
        if x.get('idempotency_key'):idem.add(key)
    return False


def _ancestry(t,e,engine):
    nodes={x.get('id'):x for x in t if isinstance(x,dict)}
    for x in t:
        if not isinstance(x,dict) or x.get('type')!='fact':continue
        for parent in x.get('parents',[]):
            p=nodes.get(parent)
            if p is None or not isinstance(p.get('at'),int) or p['at']>x.get('at',-1):return True
    return False


def _timestamp_bounds(t,e,engine):
    for x in e:
        if not isinstance(x,dict):continue
        if type(x.get('at')) is not int or x['at']<0:return True
    return False


def _relational(t,e,engine):
    nodes={x.get('id'):x for x in t if isinstance(x,dict)}
    for event in e:
        if not isinstance(event,dict):continue
        rule=engine.rules.get(event.get('action'))
        if not rule:continue
        claims={x.get('predicate'):x for x in event.get('claims',[]) if isinstance(x,dict)}
        for descendant,ancestor in rule.required_ancestry:
            d=claims.get(descendant);a=claims.get(ancestor)
            if not d or not a:continue
            d_id,a_id=d.get('witness'),a.get('witness')
            if d_id not in nodes or a_id not in nodes:continue
            stack=list(nodes[d_id].get('parents',[]));visited=set()
            while stack:
                p=stack.pop()
                if p in visited:continue
                visited.add(p)
                stack.extend(nodes[p].get('parents',[]))
            if a_id not in visited:return True
    return False


@dataclass(frozen=True)
class Guard:
    name: str
    cost: int
    detects: Callable[[list[dict],list[dict],Verifier],bool]


GUARDS=(
    Guard('schema',1,_schema),
    Guard('declaration',1,_declaration),
    Guard('outcome',2,_outcome),
    Guard('authorization',3,_authority),
    Guard('witness',4,_witness),
    Guard('freshness',4,_freshness),
    Guard('uniqueness',2,_uniqueness),
    Guard('ancestry',3,_ancestry),
    Guard('relational',5,_relational),
    Guard('timestamp',1,_timestamp_bounds),
)


@dataclass(frozen=True)
class Synthesis:
    selected: tuple[str,...]
    rounds: tuple[dict,...]
    train_negative_covered: int
    train_negative_total: int
    certified_positives: int
    cost: int

    def to_json(self):
        return dict(selected=list(self.selected),rounds=list(self.rounds),
                    train_negative_covered=self.train_negative_covered,
                    train_negative_total=self.train_negative_total,
                    certified_positives=self.certified_positives,cost=self.cost)


class Screen:
    def __init__(self,engine:Verifier,chosen:Iterable[str]=()):
        self.engine=engine
        found={x.name:x for x in GUARDS}
        chosen=tuple(chosen)
        if len(chosen)!=len(set(chosen)) or any(k not in found for k in chosen):
            raise ValueError('unknown or duplicate guard')
        self.guards=tuple(found[x] for x in chosen)

    def check(self,t:list[dict],e:list[dict]):
        """Returns REJECT or DEFER; critically NEVER returns PASS."""
        firing=[]
        for guard in self.guards:
            try:
                if guard.detects(t,e,self.engine):firing.append(guard.name)
            except (ValueError,TypeError,KeyError):
                # A guard parsing exception cannot authorize a trace.
                firing.append(guard.name+':invalid-input')
        return ('REJECT' if firing else 'DEFER',tuple(firing))

    def verified(self,t,e):
        """CAPE is authoritative; a cheap screen can only prioritize review."""
        hint=self.check(t,e)
        return hint,self.engine.evaluate(t,e)


def synthesize(engine: Verifier, positives:list[Trace], negatives:list[Trace]) -> Synthesis:
    """Deterministic counterexample-guided weighted set-cover on labeled samples.

    Exhaustive oracle verification is used only in the *offline synthesis* loop;
    selection is greedy, not a claim of globally minimum policy or soundness.
    """
    if not positives or not negatives:raise ValueError('need positive and negative cases')
    if any(engine.evaluate(*x).verdict!='PASS' for x in positives):
        raise ValueError('positive examples must be oracle-confirmed')
    if any(engine.evaluate(*x).verdict=='PASS' for x in negatives):
        raise ValueError('negative examples must not pass oracle')
    catalog={g.name:g for g in GUARDS}
    valid={g.name:g for g in GUARDS if all(not g.detects(*p,engine) for p in positives)}
    detections={name:frozenset(i for i,x in enumerate(negatives) if g.detects(*x,engine))
                for name,g in valid.items()}
    selected=[];rounds=[];covered=set()
    while len(covered)<len(negatives):
        unseen=set(range(len(negatives)))-covered
        choices=[]
        for name,guard in valid.items():
            if name in selected:continue
            adds=detections[name]&unseen
            if adds:choices.append((len(adds)/guard.cost,len(adds),-guard.cost,name,adds))
        if not choices:break
        # Greatest new coverage / estimated work, deterministic name tie-break.
        choices.sort(key=lambda z:(-z[0],-z[1],-z[2],z[3]))
        _,num,_,name,adds=choices[0]
        selected.append(name)
        covered.update(adds)
        rounds.append(dict(round=len(rounds)+1,selected=name,new_negatives=num,
                           cumulative_covered=len(covered),remaining=len(negatives)-len(covered)))
    return Synthesis(tuple(selected),tuple(rounds),len(covered),len(negatives),len(positives),
                     sum(catalog[x].cost for x in selected))
