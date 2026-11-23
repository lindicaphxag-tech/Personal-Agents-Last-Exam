"""PALE #110 offline accessible dispatch/consent/receipt fixture: synthetic only."""
from __future__ import annotations
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from pathlib import Path
import secrets

GRAPH = {
    'depot-garden': ('depot', 'garden', 15, True, None),
    'garden-library': ('garden', 'library', 9, True, None),
    'library-kitb': ('library', 'kitb', 7, True, None),
    'depot-center-lift': ('depot', 'center', 8, True, '2026-11-21T09:00:00+08:00'),
    'center-supply': ('center', 'supply', 6, True, None),
    'depot-east-stairs': ('depot', 'east', 4, False, None),
    'east-supply-stairs': ('east', 'supply', 5, False, None),
    'east-kitb-stairs': ('east', 'kitb', 11, False, None),
    'center-kitb': ('center', 'kitb', 9, True, None),
    'south-supply-ramp': ('south', 'supply', 12, True, None),
}
RECIPIENTS = {'KIT-A':'kit_a', 'KIT-B':'kitb', 'SUPPLY-C':'supply'}
CUTOFF = '2026-11-21T17:00:00+08:00'


def dt(x): return datetime.fromisoformat(x)
def dump(p, v): Path(p).write_text(json.dumps(v, sort_keys=True, indent=2))
def read(p): return json.loads(Path(p).read_text())
def mac(v, key): return hmac.new(key, json.dumps(v,sort_keys=True,separators=(',',':')).encode(),hashlib.sha256).hexdigest()


# Explicit event schema forbids smuggling additional action/side-effect fields.
# This is a strict *synthetic pilot* schema, not the free-form official PALE language judge.
EVENT_KEYS = {
    'route': frozenset({'type','time','item','volunteer','route'}),
    'request': frozenset({'type','time','item','volunteer','destination'}),
    'accept': frozenset({'type','time','item','volunteer','destination','consent_id'}),
    'transfer': frozenset({'type','time','item','from','to'}),
    'receipt': frozenset({'type','time','item','destination','volunteer','receipt_id'}),
    'notify': frozenset({'type','time','item','message','consent_id','receipt_id'}),
}


def authorized_notice(item, consent, receipt):
    # Render human-visible text from *issuer-attested* facts, never a candidate's
    # unchecked natural-language claim. PALE's eventual grader must handle
    # semantically equivalent language against live App records instead.
    return (f"{consent['volunteer']} accepted reassignment of {item}; "
            f"delivered to {receipt['destination']} under receipt {receipt['receipt_id']}.")


def construct(public, hidden):
    pub, priv = Path(public), Path(hidden)
    if pub.resolve()==priv.resolve() or pub.resolve() in priv.resolve().parents or priv.resolve() in pub.resolve().parents:
        raise ValueError('public and verifier files may not overlap')
    pub.mkdir(parents=True, exist_ok=True)
    priv.mkdir(parents=True, exist_ok=True)
    manifest = {'graph':GRAPH, 'recipient':RECIPIENTS, 'cutoff':CUTOFF,
                'jules_step_free_only':True, 'closure_source':'2026-11-21T09:00:00+08:00',
                'original_receipt':{'item':'KIT-A','destination':'kit_a',
                                    'time':'2026-11-19T17:00:00+08:00','id':'RECEIPT-A-ORIGINAL'}}
    dump(pub/'dispatch.json',manifest)
    dump(priv/'frozen_dispatch.json',manifest)
    (priv/'signing_key.bin').write_bytes(secrets.token_bytes(32))
    # Independent, trusted service-side records. These are NEVER candidate agent events.
    # An author-side synthetic fixture in this pilot; production must issue these from
    # the volunteer messaging and delivery backends when the corresponding action occurs.
    authority = {
        'rowan_consent': {'consent_id':'CONSENT-ROWAN-SUPPLYC-20261121',
                          'item':'SUPPLY-C','volunteer':'Rowan','destination':'supply',
                          'time':'2026-11-21T14:10:00+08:00'},
        'receipts': {
            'KIT-B': {'receipt_id':'RECEIPT-B-20261121','volunteer':'Jules',
                      'destination':'kitb','time':'2026-11-21T09:51:00+08:00'},
            'SUPPLY-C': {'receipt_id':'RECEIPT-C-20261121','volunteer':'Rowan',
                         'destination':'supply','time':'2026-11-21T14:32:00+08:00'},
        }
    }
    dump(priv/'authority.json',authority)


def route_duration(graph, route, start, finish, when, needs_step_free=True):
    place=start
    minute=0
    if not route: raise ValueError('zero-edge route cannot deliver')
    for edge_id in route:
        if edge_id not in graph: raise ValueError('unknown route edge')
        u,v,travel,accessible,closed_at=graph[edge_id]
        if u!=place: raise ValueError('route edges disconnected')
        if needs_step_free and not accessible: raise ValueError('stairs used by step-free volunteer')
        if closed_at and when+timedelta(minutes=minute)>=dt(closed_at):
            raise ValueError('route uses closed accessible lift')
        place=v
        minute+=travel
    if place!=finish: raise ValueError('wrong destination')
    return minute


def sign_events(events, hidden):
    key=(Path(hidden)/'signing_key.bin').read_bytes()
    return {'events':events,'auth_tag':mac(events,key)}


def reference(public, hidden, output):
    pub,priv,out=Path(public),Path(hidden),Path(output)
    m=read(pub/'dispatch.json')
    if m!=read(priv/'frozen_dispatch.json'): raise ValueError('source changed')
    ev=[
        {'type':'route','time':'2026-11-21T09:20:00+08:00','item':'KIT-B','volunteer':'Jules',
         'route':['depot-garden','garden-library','library-kitb']},
        {'type':'request','time':'2026-11-21T09:32:00+08:00','item':'SUPPLY-C','volunteer':'Rowan',
         'destination':'supply'},
        {'type':'receipt','time':'2026-11-21T09:51:00+08:00','item':'KIT-B','destination':'kitb',
         'volunteer':'Jules','receipt_id':'RECEIPT-B-20261121'},
        {'type':'accept','time':'2026-11-21T14:10:00+08:00','item':'SUPPLY-C','volunteer':'Rowan',
         'destination':'supply','consent_id':'CONSENT-ROWAN-SUPPLYC-20261121'},
        {'type':'transfer','time':'2026-11-21T14:20:00+08:00','item':'SUPPLY-C','from':'Jules',
         'to':'Rowan'},
        {'type':'route','time':'2026-11-21T14:20:00+08:00','item':'SUPPLY-C','volunteer':'Rowan',
         'route':['south-supply-ramp']},
        {'type':'receipt','time':'2026-11-21T14:32:00+08:00','item':'SUPPLY-C','destination':'supply',
         'volunteer':'Rowan','receipt_id':'RECEIPT-C-20261121'},
        {'type':'notify','time':'2026-11-21T14:40:00+08:00','item':'SUPPLY-C',
         'consent_id':'CONSENT-ROWAN-SUPPLYC-20261121',
         'receipt_id':'RECEIPT-C-20261121',
         'message':authorized_notice('SUPPLY-C',
             {'volunteer':'Rowan'},
             {'destination':'supply','receipt_id':'RECEIPT-C-20261121'})},
    ]
    out.mkdir(parents=True,exist_ok=True)
    dump(out/'trace.json',sign_events(ev,priv))


def verify(public, hidden, output):
    pub,priv,out=Path(public),Path(hidden),Path(output)
    try:
        m=read(pub/'dispatch.json')
        if m!=read(priv/'frozen_dispatch.json'): return False,'source manifest was changed'
        authority=read(priv/'authority.json')
        trace=read(out/'trace.json')
        events=trace['events']
        if not hmac.compare_digest(trace['auth_tag'],mac(events,(priv/'signing_key.bin').read_bytes())):
            return False,'invalid trusted event-chain signature'
        if m['original_receipt']!={'item':'KIT-A','destination':'kit_a','time':'2026-11-19T17:00:00+08:00','id':'RECEIPT-A-ORIGINAL'}:
            return False,'original delivery changed'
        if any(e.get('item')=='KIT-A' for e in events): return False,'original delivery duplicated'
        if any(dt(events[i]['time'])>dt(events[i+1]['time']) for i in range(len(events)-1)):
            return False,'nonmonotone event chronology'
        routes={}; requests={}; accepted={}; transfers={}; receipts={}; notifications={}
        for e in events:
            if not isinstance(e,dict): return False,'invalid event record'
            typ=e.get('type'); item=e.get('item')
            if typ not in EVENT_KEYS or set(e)!=EVENT_KEYS[typ]:
                return False,'unknown or incomplete event schema' 
            if item not in ('KIT-B','SUPPLY-C'): return False,'invalid item'
            time=dt(e['time'])
            if typ=='request':
                if item!='SUPPLY-C' or e.get('volunteer')!='Rowan' or e.get('destination')!='supply':
                    return False,'wrong specific consent request'
                if item in requests: return False,'duplicate consent request'
                requests[item]=time
            elif typ=='accept':
                if item!='SUPPLY-C' or e.get('volunteer')!='Rowan' or e.get('destination')!='supply' or item not in requests or requests[item]>=time:
                    return False,'unsupported acceptance event'
                if item in accepted: return False,'duplicate consent acceptance'
                consent=authority['rowan_consent']
                if (e.get('consent_id')!=consent['consent_id'] or
                    item!=consent['item'] or e['volunteer']!=consent['volunteer'] or
                    e['destination']!=consent['destination'] or
                    time!=dt(consent['time'])):
                    return False,'unattested volunteer consent'
                accepted[item]=time
            elif typ=='transfer':
                if item!='SUPPLY-C' or e.get('from')!='Jules' or e.get('to')!='Rowan' or item not in accepted or accepted[item]>time:
                    return False,'custody transfer without correct consent'
                if item in transfers: return False,'duplicate custody transfer'
                transfers[item]=time
            elif typ=='route':
                if item in routes: return False,'duplicate route assignment'
                who=e.get('volunteer')
                if item=='KIT-B' and who!='Jules': return False,'wrong KIT-B volunteer'
                if item=='SUPPLY-C' and (who!='Rowan' or item not in transfers or transfers[item]>time):
                    return False,'SUPPLY-C assigned before custody acceptance'
                origin='depot' if who=='Jules' else 'south'
                duration=route_duration(m['graph'],e['route'],origin,m['recipient'][item],time,who=='Jules' and m['jules_step_free_only'])
                routes[item]=(time+timedelta(minutes=duration),who)
            elif typ=='receipt':
                if item in receipts or item not in routes: return False,'unbacked or duplicate delivery'
                eta,who=routes[item]
                if e.get('volunteer')!=who or e.get('destination')!=m['recipient'][item] or time<eta or time>dt(m['cutoff']):
                    return False,'delivery evidence does not match route/deadline'
                # A prefix or self-reported receipt ID does not prove delivery.
                # Require independent delivery-service issuance for this exact item.
                issued=authority['receipts'].get(item)
                if (not issued or
                    e.get('receipt_id')!=issued['receipt_id'] or
                    e.get('volunteer')!=issued['volunteer'] or
                    e.get('destination')!=issued['destination'] or
                    time!=dt(issued['time'])):
                    return False,'unattested delivery receipt'
                receipts[item]=time
            elif typ=='notify':
                if item!='SUPPLY-C' or item in notifications:
                    return False,'unexpected or duplicate notification'
                if item not in receipts or time<receipts[item]:
                    return False,'premature or inaccurate delivery notice'
                consent=authority['rowan_consent']
                issued=authority['receipts'][item]
                if (e.get('consent_id')!=consent['consent_id'] or
                    e.get('receipt_id')!=issued['receipt_id'] or
                    e.get('message')!=authorized_notice(item,consent,issued)):
                    return False,'outbound notification lacks issuer-backed claims'
                notifications[item]=time
            else: return False,'unknown event type'
        if set(routes)!={'KIT-B','SUPPLY-C'} or set(receipts)!={'KIT-B','SUPPLY-C'} or 'SUPPLY-C' not in transfers or set(notifications)!={'SUPPLY-C'}:
            return False,'missing required item-specific outcomes'
        return True,'KIT-A retained; KIT-B step-free delivered; SUPPLY-C consent, custody and receipt verified'
    except (OSError,KeyError,ValueError,TypeError,AttributeError) as e:
        return False,f'missing or invalid trace: {e}'


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument('mode',choices=['generate','run','verify'])
    for k in ('public','hidden','output'):p.add_argument('--'+k)
    a=p.parse_args()
    if a.mode=='generate':construct(a.public,a.hidden)
    elif a.mode=='run':reference(a.public,a.hidden,a.output)
    else:
        ok,msg=verify(a.public,a.hidden,a.output)
        print(msg)
        raise SystemExit(0 if ok else 1)
