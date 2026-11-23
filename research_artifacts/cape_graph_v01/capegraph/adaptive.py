"""CAPE-Adapt: exact finite-belief active evidence acquisition.

Unlike CAPE-Plan's fixed hypothetical receipts, this planner knows only a
probability distribution over possible worlds. It chooses a read-only service
query, learns the resulting *authenticated* observation, updates the possible
worlds, and replans. The true world identity is never given to the policy.

Exact dynamic programming solves the bounded finite-belief problem; returns
expected goal value, expected query cost and a checkable decision tree.
Neither world priors nor future receipts are calibrated from field data here.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from typing import Iterable, Mapping

from .core import digest
from .planner import Goal, Witness, _grade

MAX_PROBES=9
MAX_WORLDS=24


@dataclass(frozen=True)
class Probe:
    name: str
    cost: int
    channel: str
    read_only: bool = True

    def __post_init__(self):
        if not isinstance(self.name,str) or not self.name or not isinstance(self.channel,str) or not self.channel:
            raise ValueError('probe name and channel must be non-empty')
        if type(self.cost) is not int or self.cost <= 0:
            raise ValueError('probe cost must be positive int')
        if self.read_only is not True:
            raise ValueError('active evidence probes must be read only')


@dataclass(frozen=True)
class World:
    name: str
    prior: Fraction
    responses: Mapping[str, tuple[Witness, ...]]

    def __post_init__(self):
        if not self.name or not isinstance(self.prior,Fraction) or self.prior <= 0:
            raise ValueError('worlds need a name and positive exact-rational prior')
        if not isinstance(self.responses,Mapping):
            raise ValueError('world response model must be a mapping')


@dataclass(frozen=True)
class Decision:
    query: str | None
    expected_goal_value: Fraction
    expected_query_cost: Fraction
    verified_goals_if_stop: tuple[str,...]
    branches: tuple[tuple[str,'Decision'],...]

    def as_dict(self):
        return {
            'query':self.query,
            'expected_goal_value':[self.expected_goal_value.numerator,self.expected_goal_value.denominator],
            'expected_query_cost':[self.expected_query_cost.numerator,self.expected_query_cost.denominator],
            'verified_goals_if_stop':list(self.verified_goals_if_stop),
            'branches':{k:branch.as_dict() for k,branch in self.branches},
        }


@dataclass(frozen=True)
class AdaptivePolicy:
    decision: Decision
    states_visited: int
    worlds: int
    probes: int
    budget: int

    def as_dict(self):
        payload={'decision':self.decision.as_dict(),
                 'states_visited':self.states_visited,'worlds':self.worlds,
                 'probes':self.probes,'budget':self.budget}
        payload['sha256_without_digest']=digest(payload)
        return payload


def response_id(receipts: tuple[Witness,...]) -> str:
    """Canonical observation key, independent of witness ordering."""
    records=sorted(({'token':r.token,'value':r.value,'issuer':r.issuer,'at':r.at}
                    for r in receipts),key=lambda x:(x['token'],x['issuer'],x['at'],digest(x['value'])))
    return digest(records)


def _setup(goals:Iterable[Goal],probes:Iterable[Probe],worlds:Iterable[World],
           budget:int,initial:Iterable[Witness]):
    gs=tuple(sorted(goals,key=lambda x:x.name));qs=tuple(sorted(probes,key=lambda x:x.name));ws=tuple(sorted(worlds,key=lambda x:x.name));ini=tuple(initial)
    if type(budget) is not int or budget<0 or len(qs)>MAX_PROBES or not qs:
        raise ValueError('budget must be nonnegative; 1 to 9 probes required')
    if not ws or len(ws)>MAX_WORLDS or sum((w.prior for w in ws),Fraction(0))!=1:
        raise ValueError('worlds must define a normalized exact prior')
    if len({x.name for x in gs})!=len(gs) or len({x.name for x in qs})!=len(qs) or len({x.name for x in ws})!=len(ws):
        raise ValueError('goal, query and world names must be unique')
    if any(not isinstance(x,Goal) for x in gs) or any(not isinstance(q,Probe) for q in qs):
        raise TypeError('expected typed Goal and Probe contracts')
    if any(not isinstance(x,World) for x in ws) or any(not isinstance(x,Witness) for x in ini):
        raise TypeError('expected typed World and Witness evidence')
    for world in ws:
        if set(world.responses)!={q.name for q in qs}:
            raise ValueError('every world must specify every query response')
        for q in qs:
            receipts=world.responses[q.name]
            if not isinstance(receipts,tuple) or any(not isinstance(x,Witness) or x.issuer!=q.channel for x in receipts):
                raise ValueError('world responses require correct service-bound receipts')
            if len({(x.token,x.at) for x in receipts}) != len(receipts):
                raise ValueError('duplicate service token/time receipt')
    return gs,qs,ws,ini


def solve_adaptive(goals:Iterable[Goal],probes:Iterable[Probe],worlds:Iterable[World],
                   budget:int,initial:Iterable[Witness]=()) -> AdaptivePolicy:
    """Optimal adaptive read-only query decision tree for an exact world prior.

    A policy sees only the observation equivalence class, not the world name.
    A Markov state consists of observed receipts, available query budget and the
    surviving worlds; posterior is normalized by the surviving prior masses.
    The utility is the completed conjunctive-goal reward. Tie-breaks: lower
    expected query cost, then lexicographically smallest probe identity.
    """
    gs,qs,ws,ini=_setup(goals,probes,worlds,budget,initial)
    name_to_q={q.name:q for q in qs}
    prior={w.name:w.prior for w in ws}
    cache={}

    def rec(remaining:tuple[str,...],allowed:tuple[str,...],remaining_budget:int,
            observed:tuple[Witness,...]) -> Decision:
        # All paths to a state have the same canonical observed evidence; the
        # historical identity is irrelevant after the posterior has updated.
        signature=(remaining,allowed,remaining_budget,response_id(observed))
        if signature in cache:
            return cache[signature]
        reward,verified=_grade(gs,observed)
        best=Decision(None,Fraction(reward),Fraction(0),verified,())
        total=sum((prior[name] for name in allowed),Fraction(0))
        assert total>0
        for name in remaining:
            q=name_to_q[name]
            if q.cost>remaining_budget:
                continue
            partition={}
            for world in ws:
                if world.name not in allowed:
                    continue
                obs=tuple(world.responses[name]);key=response_id(obs)
                if key not in partition:partition[key]=([],obs)
                partition[key][0].append(world.name)
            candidate_value=Fraction(0)
            candidate_cost=Fraction(q.cost)
            tree=[]
            for observation_key,(survivors,receipts) in sorted(partition.items()):
                child=rec(tuple(x for x in remaining if x!=name),tuple(sorted(survivors)),
                          remaining_budget-q.cost,observed+receipts)
                weight=sum((prior[x] for x in survivors),Fraction(0))/total
                candidate_value+=weight*child.expected_goal_value
                candidate_cost+=weight*child.expected_query_cost
                tree.append((observation_key,child))
            candidate=Decision(name,candidate_value,candidate_cost,verified,tuple(tree))
            if (candidate.expected_goal_value>best.expected_goal_value or
                (candidate.expected_goal_value==best.expected_goal_value and
                 (candidate.expected_query_cost<best.expected_query_cost or
                  (candidate.expected_query_cost==best.expected_query_cost and
                   (best.query is not None and name<best.query))))):
                best=candidate
        cache[signature]=best
        return best

    decision=rec(tuple(q.name for q in qs),tuple(w.name for w in ws),budget,ini)
    return AdaptivePolicy(decision,len(cache),len(ws),len(qs),budget)


def execute_policy(policy:AdaptivePolicy,world:World,queries:Iterable[Probe],
                   goals:Iterable[Goal],initial:Iterable[Witness]=())->tuple[int,int,tuple[str,...]]:
    """Independent realized-world replay: uses only response key, never world identity."""
    lookup={q.name:q for q in queries}
    receipts=tuple(initial)
    value=0;spent=0;choices=[]
    node=policy.decision
    while node.query is not None:
        q=lookup[node.query]
        spent+=q.cost;choices.append(q.name)
        response=tuple(world.responses[q.name]);receipts+=response
        key=response_id(response)
        children=dict(node.branches)
        if key not in children:raise AssertionError('policy omitted a possible authenticated observation')
        node=children[key]
    value,_=_grade(tuple(goals),receipts)
    return value,spent,tuple(choices)


def evaluate_fixed(goals:Iterable[Goal],probes:Iterable[Probe],worlds:Iterable[World],
                   budget:int,initial:Iterable[Witness]=())->tuple[Fraction,int,tuple[str,...]]:
    """Independent fair *nonadaptive* query subset baseline with exact prior.

    Uses the same world probabilities and budget but must commit to a query set
    before receiving any outcomes. Reports maximum expected achieved-goal value.
    """
    gs,qs,ws,ini=_setup(goals,probes,worlds,budget,initial)
    best=(Fraction(-1),10**9,())
    for count in range(len(qs)+1):
        for chosen in combinations(qs,count):
            spent=sum(q.cost for q in chosen)
            if spent>budget:continue
            value=sum((w.prior*_grade(gs,ini+tuple(receipt for q in chosen for receipt in w.responses[q.name]))[0]
                       for w in ws),Fraction(0))
            if (-value,spent,tuple(q.name for q in chosen))<(-best[0],best[1],best[2]):
                best=(value,spent,tuple(q.name for q in chosen))
    return best


def expected_replay(policy:AdaptivePolicy,worlds:Iterable[World],probes:Iterable[Probe],
                   goals:Iterable[Goal],initial:Iterable[Witness]=())->tuple[Fraction,Fraction]:
    """Check DP reported expectation by independent world-by-world policy execution."""
    reward=cost=Fraction(0)
    for w in worlds:
        r,c,_=execute_policy(policy,w,probes,goals,initial)
        reward+=w.prior*r;cost+=w.prior*c
    return reward,cost


def brute_force_adaptive_oracle(goals:Iterable[Goal],probes:Iterable[Probe],worlds:Iterable[World],
                                 budget:int,initial:Iterable[Witness]=())->tuple[Fraction,Fraction]:
    """Independent, non-memoized exhaustive Bellman recursion for <= 5 probes.

    This test oracle enumerates every possible next query over every distinct
    observation, conditioning the exact prior on the observed world partition.
    It is deliberately implemented separately from the production DP cache.
    """
    gs,qs,ws,ini=_setup(goals,probes,worlds,budget,initial)
    if len(qs)>5 or len(ws)>5:raise ValueError('oracle limited to 5 probes/worlds')

    def choose(available:tuple[Probe,...],possible:tuple[World,...],left:int,
               receipts:tuple[Witness,...])->tuple[Fraction,Fraction]:
        score,_=_grade(gs,receipts)
        best_score=Fraction(score);best_cost=Fraction(0)
        mass=sum((x.prior for x in possible),Fraction(0))
        for probe in available:
            if probe.cost>left:continue
            groups={}
            for w in possible:
                seen=w.responses[probe.name]
                k=response_id(seen)
                if k not in groups:groups[k]=([],seen)
                groups[k][0].append(w)
            next_queries=tuple(p for p in available if p.name!=probe.name)
            value=Fraction(0);expected_cost=Fraction(probe.cost)
            for survivors,observation in groups.values():
                mv=sum((x.prior for x in survivors),Fraction(0))
                v,c=choose(next_queries,tuple(survivors),left-probe.cost,receipts+observation)
                value+=mv/mass*v
                expected_cost+=mv/mass*c
            if value>best_score or (value==best_score and expected_cost<best_cost):
                best_score,best_cost=value,expected_cost
        return best_score,best_cost

    return choose(qs,ws,budget,ini)
