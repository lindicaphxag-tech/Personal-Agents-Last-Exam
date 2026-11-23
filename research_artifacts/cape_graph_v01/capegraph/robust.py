"""CAPE-Robust v0.4: globally coupled prior-robust evidence acquisition.

Solve a *finite deterministic-policy* max-min verification problem, with nature
choosing ONE prior distribution for the ENTIRE rollout. A naive stagewise
minimization would silently replace this with rectangular adversarial priors.

The Pareto frontier carries one realized reward and one cost per latent world,
not just posterior expected values. Only componentwise safe dominance is used.
This is an exact exhaustive research oracle for small problems, not an
asymptotically efficient robust POMDP solver nor authenticated deployment.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from typing import Iterable, Mapping

from .adaptive import Probe, World, _setup, response_id
from .planner import Goal, Witness, _grade
from .core import digest

MAX_WORLD_COUNT = 6
MAX_QUERY_COUNT = 6
MAX_PRIORS = 12
MAX_FRONTIER = 24000


@dataclass(frozen=True)
class Prior:
    name: str
    probabilities: Mapping[str, Fraction]


@dataclass(frozen=True)
class RobustDecision:
    query: str | None
    branches: tuple[tuple[str, 'RobustDecision'], ...] = ()

    def as_dict(self) -> dict:
        return {'query': self.query,
                'branches': {key: child.as_dict() for key, child in self.branches}}


@dataclass(frozen=True)
class RobustPolicy:
    decision: RobustDecision
    worst_case_reward: Fraction
    worst_case_cost: Fraction
    scenario_rewards: tuple[tuple[str, Fraction], ...]
    scenario_costs: tuple[tuple[str, Fraction], ...]
    per_world_rewards: tuple[tuple[str, int], ...]
    per_world_costs: tuple[tuple[str, int], ...]
    frontier_size: int
    states_expanded: int

    def as_dict(self) -> dict:
        d = {'decision': self.decision.as_dict(),
             'worst_case_reward': str(self.worst_case_reward),
             'worst_case_cost': str(self.worst_case_cost),
             'scenario_rewards': {k: str(v) for k, v in self.scenario_rewards},
             'scenario_costs': {k: str(v) for k, v in self.scenario_costs},
             'per_world_rewards': dict(self.per_world_rewards),
             'per_world_costs': dict(self.per_world_costs),
             'frontier_size': self.frontier_size,
             'states_expanded': self.states_expanded}
        d['sha256_without_digest'] = digest(d)
        return d


@dataclass(frozen=True)
class _Candidate:
    rewards: tuple[int, ...]
    costs: tuple[int, ...]
    policy: RobustDecision


def _contract(goals: Iterable[Goal], probes: Iterable[Probe],
              worlds: Iterable[World], budget: int, priors: Iterable[Prior],
              initial: Iterable[Witness]):
    gs, qs, ws, ini = _setup(goals, probes, worlds, budget, initial)
    if len(ws) > MAX_WORLD_COUNT or len(qs) > MAX_QUERY_COUNT:
        raise ValueError('exact robust search limited to 6 worlds and 6 queries')
    pset = tuple(sorted(priors, key=lambda x: x.name))
    if not (1 <= len(pset) <= MAX_PRIORS) or any(not isinstance(p, Prior) for p in pset):
        raise ValueError('require 1..12 valid prior scenarios')
    if len({p.name for p in pset}) != len(pset) or any(not p.name for p in pset):
        raise ValueError('prior names must be distinct and nonempty')
    keys = {w.name for w in ws}
    for p in pset:
        if not isinstance(p.probabilities, Mapping) or set(p.probabilities) != keys:
            raise ValueError('all priors must assign every world')
        vals = tuple(p.probabilities[w.name] for w in ws)
        if any(not isinstance(x, Fraction) or x < 0 for x in vals):
            raise ValueError('prior probabilities must be nonnegative exact rationals')
        if sum(vals, Fraction(0)) != 1:
            raise ValueError('prior probabilities must sum exactly to one')
    return gs, qs, ws, ini, pset


def _signature(p: RobustDecision) -> tuple:
    return (p.query or '', tuple((k, _signature(v)) for k, v in p.branches))


def _prune(candidates: list[_Candidate]) -> tuple[_Candidate, ...]:
    """Keep Pareto policies. Componentwise reward/cost dominance is globally safe."""
    out: list[_Candidate] = []
    candidates.sort(key=lambda x: (-sum(x.rewards), sum(x.costs), _signature(x.policy)))
    for candidate in candidates:
        dominated = False
        to_remove = []
        for i, current in enumerate(out):
            a = (all(x >= y for x, y in zip(current.rewards, candidate.rewards))
                 and all(x <= y for x, y in zip(current.costs, candidate.costs)))
            b = (all(x >= y for x, y in zip(candidate.rewards, current.rewards))
                 and all(x <= y for x, y in zip(candidate.costs, current.costs)))
            if a:
                dominated = True
                break
            if b:
                to_remove.append(i)
        if dominated:
            continue
        for i in reversed(to_remove):
            out.pop(i)
        out.append(candidate)
        if len(out) > MAX_FRONTIER:
            raise ValueError('robust exact Pareto frontier exceeded capacity')
    return tuple(out)


def _enumerate(gs, qs, ws, initial, budget, prune=True):
    qmap = {q.name: q for q in qs}
    wmap = {w.name: w for w in ws}
    memo = {}
    expanded = 0

    def rec(available: tuple[str, ...], possible: tuple[str, ...], left: int,
            receipts: tuple[Witness, ...]):
        nonlocal expanded
        state = (available, possible, left, response_id(receipts))
        if prune and state in memo:
            return memo[state]
        expanded += 1
        current_value, _ = _grade(gs, receipts)
        candidates = [_Candidate(tuple(current_value for _ in possible),
                                 tuple(0 for _ in possible), RobustDecision(None))]
        for name in available:
            q = qmap[name]
            if q.cost > left:
                continue
            grouped = {}
            for world_name in possible:
                response = tuple(wmap[world_name].responses[name])
                key = response_id(response)
                if key not in grouped:
                    grouped[key] = ([], response)
                grouped[key][0].append(world_name)
            branches = []
            for key, (survivors, response) in sorted(grouped.items()):
                sub = rec(tuple(x for x in available if x != name),
                          tuple(survivors), left-q.cost, receipts+response)
                branches.append((key, tuple(survivors), sub))
            # One continuation is selected independently for each observed reply.
            for selection in product(*(branch[2] for branch in branches)):
                rewards_by_world = {}
                costs_by_world = {}
                for (_key, survivors, _options), option in zip(branches, selection):
                    for w, reward, cost in zip(survivors, option.rewards, option.costs):
                        rewards_by_world[w] = reward
                        costs_by_world[w] = q.cost + cost
                candidate = _Candidate(
                    tuple(rewards_by_world[w] for w in possible),
                    tuple(costs_by_world[w] for w in possible),
                    RobustDecision(name, tuple((branch[0], option.policy)
                                               for branch, option in zip(branches, selection))))
                candidates.append(candidate)
                if len(candidates) > MAX_FRONTIER * 10:
                    raise ValueError('robust exact cross-product exceeded capacity')
        frontier = _prune(candidates) if prune else tuple(candidates)
        if prune:
            memo[state] = frontier
        return frontier

    result = rec(tuple(q.name for q in qs), tuple(w.name for w in ws), budget, initial)
    return result, expanded


def _metrics(c: _Candidate, ws: tuple[World, ...], pset: tuple[Prior, ...]):
    rewards = tuple((p.name, sum((p.probabilities[w.name]*v for w, v in zip(ws, c.rewards)), Fraction(0)))
                    for p in pset)
    costs = tuple((p.name, sum((p.probabilities[w.name]*v for w, v in zip(ws, c.costs)), Fraction(0)))
                  for p in pset)
    return min(x[1] for x in rewards), max(x[1] for x in costs), rewards, costs


def solve_robust(goals: Iterable[Goal], probes: Iterable[Probe],
                 worlds: Iterable[World], budget: int, priors: Iterable[Prior],
                 initial: Iterable[Witness] = ()) -> RobustPolicy:
    """Exact max-min reward across a fixed *globally coupled* set of priors.

    The adversary chooses one prior *before* a complete rollout. It cannot
    switch priors independently after each observation. Only deterministic
    policies are considered; mixed strategies can improve max-min value.
    """
    gs, qs, ws, ini, pset = _contract(goals, probes, worlds, budget, priors, initial)
    candidates, expanded = _enumerate(gs, qs, ws, ini, budget, prune=True)
    best = min(candidates, key=lambda c: (
        -_metrics(c, ws, pset)[0], _metrics(c, ws, pset)[1], _signature(c.policy)))
    worst, cost, rewards, costs = _metrics(best, ws, pset)
    return RobustPolicy(best.policy, worst, cost, rewards, costs,
                        tuple((w.name, val) for w, val in zip(ws, best.rewards)),
                        tuple((w.name, val) for w, val in zip(ws, best.costs)),
                        len(candidates), expanded)


def exhaustive_independent_reference(goals: Iterable[Goal], probes: Iterable[Probe],
                                     worlds: Iterable[World], budget: int, priors: Iterable[Prior],
                                     initial: Iterable[Witness] = ()) -> tuple[Fraction, Fraction]:
    """Separately written enumeration of every deterministic decision tree.

    No Pareto pruning, policy-state memoization, or production candidate structs.
    Limited to four probes/four worlds to avoid combinatorial blow-up.
    """
    gs, qs, ws, ini, pset = _contract(goals, probes, worlds, budget, priors, initial)
    if len(qs) > 4 or len(ws) > 4:
        raise ValueError('independent oracle limited to four probes and four worlds')

    def recurse(options, possible, remaining_budget, observed):
        value = _grade(gs, observed)[0]
        result = [{w.name: (value, 0) for w in possible}]  # stop action
        for q in options:
            if q.cost > remaining_budget:
                continue
            observed_classes = {}
            for w in possible:
                response = w.responses[q.name]
                key = response_id(response)
                if key not in observed_classes:
                    observed_classes[key] = ([], response)
                observed_classes[key][0].append(w)
            continuations = []
            for _key, (members, response) in sorted(observed_classes.items()):
                continuations.append(recurse(tuple(x for x in options if x.name != q.name),
                                             tuple(members), remaining_budget-q.cost,
                                             observed + response))
            for child_choice in product(*continuations):
                realized = {}
                for child in child_choice:
                    for name, (score, spent) in child.items():
                        realized[name] = (score, spent + q.cost)
                result.append(realized)
        return result

    policies = recurse(qs, ws, budget, ini)
    values = []
    for policy in policies:
        minimum = min(sum((p.probabilities[w.name]*policy[w.name][0] for w in ws), Fraction(0))
                      for p in pset)
        maximum_cost = max(sum((p.probabilities[w.name]*policy[w.name][1] for w in ws), Fraction(0))
                           for p in pset)
        values.append((minimum, maximum_cost))
    reward, cost = min(values, key=lambda x: (-x[0], x[1]))
    return reward, cost


def robust_fixed_reference(goals: Iterable[Goal], probes: Iterable[Probe],
                           worlds: Iterable[World], budget: int, priors: Iterable[Prior],
                           initial: Iterable[Witness] = ()) -> tuple[Fraction, tuple[str, ...]]:
    """Brute-force precommitted query subset, same globally fixed ambiguous priors."""
    from itertools import combinations
    gs, qs, ws, ini, pset = _contract(goals, probes, worlds, budget, priors, initial)
    variants = []
    for count in range(len(qs)+1):
        for chosen in combinations(qs, count):
            if sum(x.cost for x in chosen) > budget:
                continue
            scores = [ _grade(gs, ini+tuple(r for q in chosen for r in w.responses[q.name]))[0]
                       for w in ws]
            worst = min(sum((p.probabilities[w.name]*v for w,v in zip(ws,scores)), Fraction(0))
                        for p in pset)
            variants.append((worst, sum(x.cost for x in chosen), tuple(x.name for x in chosen)))
    best = min(variants, key=lambda x: (-x[0], x[1], x[2]))
    return best[0], best[2]


def replay_robust(policy: RobustPolicy, world: World, probes: Iterable[Probe],
                  goals: Iterable[Goal], initial: Iterable[Witness] = ()) -> tuple[int,int]:
    """Independent world-conditioned policy replay; policy never sees world ID."""
    qmap = {p.name: p for p in probes}
    node = policy.decision
    receipts = tuple(initial)
    spent = 0
    seen = set()
    while node.query is not None:
        if node.query in seen:
            raise AssertionError('repeated query in robust decision tree')
        seen.add(node.query)
        probe = qmap[node.query]
        spent += probe.cost
        response = world.responses[node.query]
        receipts += response
        node = dict(node.branches)[response_id(response)]
    return _grade(tuple(goals), receipts)[0], spent
