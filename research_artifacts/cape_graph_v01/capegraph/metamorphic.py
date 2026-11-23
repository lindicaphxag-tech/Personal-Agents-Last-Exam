"""Deterministic alpha-renaming and event-order metamorphic transformations.

Maintains the *same fictional scenario semantics* while changing surface IDs,
subjects, action scopes, grant IDs and event order. This is not independent
external data; its purpose is to catch hardcoded fixture-identity checks.
"""
from __future__ import annotations
from copy import deepcopy
import random
from .core import digest


def rename_world(trusted:list[dict],effects:list[dict],seed:int):
    if type(seed) is not int or seed<0:raise ValueError('seed must be a nonnegative integer')
    t,e=deepcopy((trusted,effects))
    rng=random.Random(seed)
    ids={x['id']:f"id-{seed}-{i}-{digest(x['id'])[:10]}" for i,x in enumerate(t+e)}
    subjects=sorted(set([x['subject'] for x in t if x['type']=='fact']+
                        [x['scope'] for x in t if x['type']=='grant']+
                        [x['scope'] for x in e]+[c['subject'] for x in e for c in x['claims']]))
    mapping={s:f"sub-{seed}-{i}" for i,s in enumerate(subjects)}
    for x in t:
        x['id']=ids[x['id']]
        if x['type']=='fact':
            x['subject']=mapping[x['subject']]
            x['parents']=[ids[p] for p in x['parents']]
        elif x['type']=='grant':x['scope']=mapping[x['scope']]
        elif x['type']=='revoke':x['grant_id']=ids[x['grant_id']]
    for x in e:
        x['id']=ids[x['id']]
        x['scope']=mapping[x['scope']]
        x['grant_id']=ids.get(x['grant_id'],x['grant_id'])
        x['idempotency_key']=f"k-{seed}-{x['id']}" if x['idempotency_key'] else ''
        for c in x['claims']:
            c['subject']=mapping[c['subject']]
            c['witness']=ids.get(c['witness'],c['witness'])
    rng.shuffle(t)
    rng.shuffle(e)
    return t,e
