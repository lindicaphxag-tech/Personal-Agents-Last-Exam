"""CAPE-Mix: exact two-prior randomized evidence-query policies.

Nature chooses a prior before seeing a *private* policy randomization coin.
Under these assumptions the finite max-min game can need randomization even
though each pure policy is an exact read-only adaptive evidence-query tree.

This module solves the two-prior zero-sum game with Fraction arithmetic,
produces an exact primal/dual certificate, and explicitly rejects >2 priors.
It is a domain-specific integration of classical finite-game minimax theory,
NOT a new general theory of robust POMDPs.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations
from typing import Iterable

from .adaptive import Probe, World, response_id
from .core import digest
from .planner import Goal, Witness
from .robust import (Prior, RobustDecision, _contract, _enumerate,
                     _metrics, _signature, replay_robust, RobustPolicy)

MAX_MIX_CANDIDATES = 1400


@dataclass(frozen=True)
class MixSupport:
    probability: Fraction
    decision: RobustDecision
    scenario_rewards: tuple[Fraction, Fraction]
    scenario_costs: tuple[Fraction, Fraction]

    def as_dict(self) -> dict:
        return {'probability': str(self.probability),
                'decision': self.decision.as_dict(),
                'scenario_rewards': [str(x) for x in self.scenario_rewards],
                'scenario_costs': [str(x) for x in self.scenario_costs]}


@dataclass(frozen=True)
class MixedPolicy:
    support: tuple[MixSupport, ...]
    guaranteed_reward: Fraction
    max_expected_cost: Fraction
    scenario_rewards: tuple[tuple[str, Fraction], ...]
    scenario_costs: tuple[tuple[str, Fraction], ...]
    # Nature's dual equilibrium: a mixture of the two candidate priors.
    dual_prior_weights: tuple[Fraction, Fraction]
    dual_upper_bound: Fraction
    frontier_size: int
    states_expanded: int

    def as_dict(self) -> dict:
        data = {'support': [x.as_dict() for x in self.support],
                'guaranteed_reward': str(self.guaranteed_reward),
                'max_expected_cost': str(self.max_expected_cost),
                'scenario_rewards': {k: str(v) for k, v in self.scenario_rewards},
                'scenario_costs': {k: str(v) for k, v in self.scenario_costs},
                'dual_prior_weights': [str(x) for x in self.dual_prior_weights],
                'dual_upper_bound': str(self.dual_upper_bound),
                'frontier_size': self.frontier_size,
                'states_expanded': self.states_expanded}
        data['sha256_without_digest'] = digest(data)
        return data


def _vectors(candidate, worlds, priors):
    _, _, rewards, costs = _metrics(candidate, worlds, priors)
    return tuple(x[1] for x in rewards), tuple(x[1] for x in costs)


def _mixture_optimum(payoffs, costs):
    """Exact upper convex-envelope optimizer for a two-column zero-sum game.

    An optimal player mixture is supported by <=2 pure strategies. Each
    pair's min of two affine reward curves has its maximum at an endpoint or
    at their intersection. Rational arithmetic avoids numerical tolerances.
    """
    if not payoffs or any(len(x) != 2 for x in payoffs):
        raise ValueError('payoffs must be a nonempty 2-column table')
    if len(payoffs) != len(costs) or any(len(x) != 2 for x in costs):
        raise ValueError('cost vectors must match the payoff table')
    if len(payoffs) > MAX_MIX_CANDIDATES:
        raise ValueError('too many exact mixed-policy candidates')
    best = None
    for i in range(len(payoffs)):
        for j in range(i, len(payoffs)):
            a, b = payoffs[i], payoffs[j]
            deltas = (a[0] - a[1], b[0] - b[1])
            candidates = (Fraction(1),) if i == j else [Fraction(0), Fraction(1)]
            if i != j and deltas[0] != deltas[1]:
                crossing = -deltas[1] / (deltas[0] - deltas[1])
                if 0 < crossing < 1:
                    candidates.append(crossing)
            for t in candidates:
                # The first pure policy is i; the second is j.
                p0 = t * a[0] + (1-t) * b[0]
                p1 = t * a[1] + (1-t) * b[1]
                cost0 = t * costs[i][0] + (1-t) * costs[j][0]
                cost1 = t * costs[i][1] + (1-t) * costs[j][1]
                score = min(p0, p1)
                max_cost = max(cost0, cost1)
                # Deterministic stable tie breaking, prefer smaller support.
                active = tuple((k, w) for k, w in ((i, t), (j, 1-t)) if w > 0)
                if i == j:
                    active = ((i, Fraction(1)),)
                elif len(active) == 1:
                    active = ((active[0][0], Fraction(1)),)
                key = (-score, max_cost, len(active), active)
                if best is None or key < best[0]:
                    best = (key, active, (p0, p1), (cost0, cost1))
    assert best is not None
    return best[1], best[2], best[3]


def _exact_dual(payoffs: tuple[tuple[Fraction, Fraction], ...],
                game_value: Fraction):
    """Derive a checkable dual upper bound with a single GLOBAL adversary prior.

    For lambda=P(scenario0), every pure policy must have expected reward <=V.
    Each policy yields a linear lower/upper restriction on lambda. Feasible
    intersection certifies weak/strong minimax duality exactly in rationals.
    """
    lo, hi = Fraction(0), Fraction(1)
    for p0, p1 in payoffs:
        delta = p0-p1
        if delta == 0:
            if p1 > game_value:
                raise AssertionError('unattainable dual value')
            continue
        threshold = (game_value-p1)/delta
        if delta > 0:
            hi = min(hi, threshold)
        else:
            lo = max(lo, threshold)
    if lo > hi:
        raise AssertionError('primal-dual gap: mixed candidate set incomplete')
    lambda_ = lo
    upper = max(lambda_*p0 + (1-lambda_)*p1 for p0, p1 in payoffs)
    if upper != game_value:
        raise AssertionError('exact primal/dual mismatch')
    return (lambda_, 1-lambda_), upper


def solve_mixed(goals: Iterable[Goal], probes: Iterable[Probe],
                worlds: Iterable[World], budget: int,
                priors: Iterable[Prior], initial: Iterable[Witness] = ()) -> MixedPolicy:
    """Two-prior optimal hidden-root-randomization policy, with exact certificate.

    A private random coin is sampled BEFORE the first query. Nature must not
    learn the coin; otherwise it can choose a different prior per sampled tree
    and randomized max-min guarantees do not hold. All eligible read-only
    queries are bound by the same pathwise budget for every pure policy.
    """
    gs, qs, ws, ini, pset = _contract(goals, probes, worlds, budget, priors, initial)
    if len(pset) != 2:
        raise ValueError('CAPE-Mix exact solver requires exactly 2 priors')
    candidates, expanded = _enumerate(gs, qs, ws, ini, budget, prune=True)
    if len(candidates) > MAX_MIX_CANDIDATES:
        raise ValueError('frontier exceeds exact 2-prior mix cap')
    pairs = tuple(_vectors(c, ws, pset) for c in candidates)
    payoff = tuple(x[0] for x in pairs)
    costs = tuple(x[1] for x in pairs)
    active, rewards, spent = _mixture_optimum(payoff, costs)
    value = min(rewards)
    dual, upper = _exact_dual(payoff, value)
    # Certificates include each component's prior-scenario reward and cost.
    support = tuple(MixSupport(weight, candidates[i].policy, payoff[i], costs[i])
                    for i, weight in active)
    if sum((x.probability for x in support), Fraction(0)) != 1:
        raise AssertionError('invalid mixture normalization')
    return MixedPolicy(support, value, max(spent),
                       tuple((p.name, v) for p,v in zip(pset, rewards)),
                       tuple((p.name, v) for p,v in zip(pset, spent)),
                       dual, upper, len(candidates), expanded)


def independent_replay(policy: MixedPolicy, worlds: Iterable[World],
                       probes: Iterable[Probe], goals: Iterable[Goal],
                       priors: Iterable[Prior], initial: Iterable[Witness] = ()) -> tuple[Fraction, Fraction]:
    """Replay each pure tree against every world; recompute root coin expectation."""
    ws = tuple(sorted(worlds, key=lambda w:w.name))
    ps = tuple(sorted(priors, key=lambda p:p.name))
    expected_reward = []
    expected_cost = []
    for p in ps:
        value = cost = Fraction(0)
        for part in policy.support:
            dummy = RobustPolicy(part.decision, Fraction(0), Fraction(0), (), (), (), (), 0, 0)
            for w in ws:
                r,c = replay_robust(dummy, w, probes, goals, initial)
                value += part.probability*p.probabilities[w.name]*r
                cost += part.probability*p.probabilities[w.name]*c
        expected_reward.append(value)
        expected_cost.append(cost)
    if tuple(expected_reward) != tuple(v for _,v in policy.scenario_rewards):
        raise AssertionError('mixed reward mismatch in independent world replay')
    if tuple(expected_cost) != tuple(v for _,v in policy.scenario_costs):
        raise AssertionError('mixed cost mismatch in independent world replay')
    return min(expected_reward), max(expected_cost)


def exact_two_prior_game_reference(payoffs, costs):
    """Independently solve a small matrix game via scipy's general LP solver.

    This is an optional TEST oracle, not a runtime dependency of CAPE-Mix.
    Floating solver tolerance is only used for independent benchmarking, never
    in the production exact rational certificate.
    """
    from scipy.optimize import linprog
    import numpy as np
    rewards = np.array([[float(z) for z in p] for p in payoffs])
    n = len(rewards)
    A = np.concatenate((-rewards.T, np.ones((2,1))), axis=1)
    c = [0.]*n + [-1.]
    constraints = np.array(A)
    objective = linprog(c, A_ub=constraints, b_ub=[0.,0.],
                        A_eq=[[1.]*n+[0.]], b_eq=[1.],
                        bounds=[(0.,1.)]*n+[(None,None)], method='highs')
    if not objective.success:
        raise AssertionError('independent simplex oracle failed: '+objective.message)
    return objective.x[-1]
