"""CAPE-Plan: exact budgeted acquisition of trusted evidence for conjunctive goals.

This is a *read-only planning* algorithm; predictions of potential witness values
are NOT authoritative evidence. A trusted adapter must execute planned queries,
authenticate service-channel receipts, and run the CAPE-Graph verifier anew.

Problem: given time/issuer/value-scoped obligations, read-only evidence queries,
query costs and a budget, maximize the total value of entirely proven goals.
Unlike ordinary set coverage, each goal is a conjunction of several needs and
latest-time contradictory evidence can invalidate an older positive witness.
The exact search uses a safe optimistic upper bound and cost-aware pruning.
Worst-case work is exponential in candidate count (limited to 20 by design).
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

from .core import canonical, digest

MAX_QUERIES = 20


@dataclass(frozen=True)
class Need:
    token: str
    expected: object
    issuers: tuple[str, ...]
    not_before: int
    not_after: int

    def __post_init__(self):
        if not self.token or not self.issuers or not all(self.issuers):
            raise ValueError("need must identify a token and trusted issuer(s)")
        if len(set(self.issuers)) != len(self.issuers):
            raise ValueError("duplicate issuers in need")
        if type(self.not_before) is not int or type(self.not_after) is not int or not 0 <= self.not_before <= self.not_after:
            raise ValueError("invalid evidence time interval")
        canonical(self.expected)  # reject non-JSON / non-finite expected values


@dataclass(frozen=True)
class Goal:
    name: str
    needs: tuple[Need, ...]
    value: int

    def __post_init__(self):
        if not self.name or not self.needs or type(self.value) is not int or self.value <= 0:
            raise ValueError("goals require a name, nonempty evidence and positive integer value")
        if len({n.token for n in self.needs}) != len(self.needs):
            raise ValueError("a single goal cannot use ambiguous duplicate tokens")


@dataclass(frozen=True)
class Witness:
    token: str
    value: object
    issuer: str
    at: int

    def __post_init__(self):
        if not self.token or not self.issuer or type(self.at) is not int or self.at < 0:
            raise ValueError("invalid witness identity/time")
        canonical(self.value)


@dataclass(frozen=True)
class Query:
    name: str
    cost: int
    channel: str
    receipts: tuple[Witness, ...]
    read_only: bool = True

    def __post_init__(self):
        if not self.name or not self.channel or type(self.cost) is not int or self.cost <= 0:
            raise ValueError("query needs an identity, channel and positive integer cost")
        if not self.read_only:
            raise ValueError("acquisition queries must be read-only")
        if any(w.issuer != self.channel for w in self.receipts):
            raise ValueError("query receipts must be bound to the query's source channel")
        if len({(w.token, w.at) for w in self.receipts}) != len(self.receipts):
            raise ValueError("query has duplicate token/time receipts")


@dataclass(frozen=True)
class Plan:
    selected: tuple[str, ...]
    cost: int
    value: int
    verified_goals: tuple[str, ...]
    pending_goals: tuple[str, ...]
    explored_leaves: int
    pruned_branches: int
    optimal: bool
    search_space: int

    def as_dict(self) -> dict:
        d = {"selected": list(self.selected), "cost": self.cost, "value": self.value,
             "verified_goals": list(self.verified_goals), "pending_goals": list(self.pending_goals),
             "explored_leaves": self.explored_leaves, "pruned_branches": self.pruned_branches,
             "optimal": self.optimal, "search_space": self.search_space}
        d["sha256_without_digest"] = digest(d)
        return d


def _validate(goals: Iterable[Goal], queries: Iterable[Query], budget: int,
              initial: Iterable[Witness]) -> tuple[tuple[Goal, ...], tuple[Query, ...], tuple[Witness, ...]]:
    gs, qs, ini = tuple(goals), tuple(queries), tuple(initial)
    if type(budget) is not int or budget < 0 or len(qs) > MAX_QUERIES:
        raise ValueError("budget must be nonnegative and at most 20 candidate queries")
    if len({g.name for g in gs}) != len(gs) or len({q.name for q in qs}) != len(qs):
        raise ValueError("goal/query identifiers must be unique")
    if any(not isinstance(x, Goal) for x in gs) or any(not isinstance(x, Query) for x in qs):
        raise TypeError("require typed Goal/Query contracts")
    if any(not isinstance(w, Witness) for w in ini):
        raise TypeError("initial witnesses must come from a trusted caller")
    return tuple(sorted(gs, key=lambda x: x.name)), tuple(sorted(qs, key=lambda x: x.name)), ini


def _satisfies(need: Need, witnesses: Iterable[Witness]) -> bool:
    current = [w for w in witnesses if w.token == need.token and w.issuer in need.issuers
               and need.not_before <= w.at <= need.not_after]
    if not current:
        return False
    newest = max(w.at for w in current)
    newest_values = {canonical(w.value) for w in current if w.at == newest}
    return newest_values == {canonical(need.expected)}


def _grade(goals: tuple[Goal, ...], witnesses: Iterable[Witness]) -> tuple[int, tuple[str, ...]]:
    seen = tuple(witnesses)
    passed = tuple(g.name for g in goals if all(_satisfies(n, seen) for n in g.needs))
    value = sum(g.value for g in goals if g.name in passed)
    return value, passed


def _make_plan(gs: tuple[Goal, ...], selection: tuple[Query, ...], initial: tuple[Witness, ...],
               leaves: int, pruned: int, optimal: bool, search_space: int) -> Plan:
    witnesses = initial + tuple(w for q in selection for w in q.receipts)
    value, names = _grade(gs, witnesses)
    selected = tuple(sorted(q.name for q in selection))
    return Plan(selected, sum(q.cost for q in selection), value, names,
                tuple(g.name for g in gs if g.name not in names), leaves, pruned, optimal, search_space)


def solve_exact(goals: Iterable[Goal], queries: Iterable[Query], budget: int,
                initial: Iterable[Witness] = ()) -> Plan:
    """Provably maximize goal value under the enumerated read-only query budget.

    Secondary objectives: minimum cost, then lexicographically earliest query IDs.
    The upper bound ignores harmful evidence and all query costs, so it may be
    loose but can never prune an actual optimum.
    """
    gs, qs, ini = _validate(goals, queries, budget, initial)
    n = len(qs)
    # For a goal to be achievable, each need must have a matching witness in
    # the chosen evidence OR some yet-unconsidered query. This necessary-only
    # condition is a safe upper bound even with superseding negative records.
    attainable: dict[tuple[int, str], bool] = {}
    for k in range(n + 1):
        available = ini + tuple(w for q in qs[k:] for w in q.receipts)
        for g in gs:
            for need in g.needs:
                key = (k, _need_id(need))
                attainable[key] = any(_positive(need, w) for w in available)

    best: Plan | None = None
    leaves = 0
    pruned = 0

    def walk(i: int, picked: tuple[Query, ...], receipts: tuple[Witness, ...], spent: int):
        nonlocal best, leaves, pruned
        available = ini + receipts
        # Safe upper bound: every unsatisfied need must be present as a
        # value/issuer/time-valid receipt in the current+remaining union.
        potential = 0
        for g in gs:
            if all(_satisfies(need, available) or attainable[(i, _need_id(need))]
                   for need in g.needs):
                potential += g.value
        if best is not None and (potential < best.value or (potential == best.value and spent > best.cost)):
            pruned += 1
            return
        if i == n:
            leaves += 1
            plan = _make_plan(gs, picked, ini, leaves, pruned, True, 1 << n)
            if best is None or (-plan.value, plan.cost, plan.selected) < (-best.value, best.cost, best.selected):
                best = plan
            return
        # Include first to discover high-value solutions early.
        q = qs[i]
        if spent + q.cost <= budget:
            walk(i + 1, picked + (q,), receipts + q.receipts, spent + q.cost)
        walk(i + 1, picked, receipts, spent)

    walk(0, (), (), 0)
    if best is None:
        raise AssertionError("empty selection must always be feasible")
    # Search statistics are global and refer to the completed proof search.
    return Plan(best.selected, best.cost, best.value, best.verified_goals,
                best.pending_goals, leaves, pruned, True, 1 << n)


def _positive(need: Need, witness: Witness) -> bool:
    return (need.token == witness.token and witness.issuer in need.issuers
            and need.not_before <= witness.at <= need.not_after
            and canonical(need.expected) == canonical(witness.value))


def _need_id(need: Need) -> str:
    return digest({"token": need.token, "expected": need.expected, "issuers": need.issuers,
                   "from": need.not_before, "through": need.not_after})


def greedy_marginal(goals: Iterable[Goal], queries: Iterable[Query], budget: int,
                    initial: Iterable[Witness] = ()) -> Plan:
    """Transparent myopic baseline: choose best immediate completed-goal gain/cost.

    It cannot value partial conjunctions. It is intentionally simple and not
    claimed to represent published planning or verification algorithms.
    """
    gs, qs, ini = _validate(goals, queries, budget, initial)
    picked: tuple[Query, ...] = ()
    current_value, _ = _grade(gs, ini)
    remain = list(qs)
    inspected = 0
    while remain:
        candidates = []
        history = ini + tuple(w for q in picked for w in q.receipts)
        for q in remain:
            if sum(x.cost for x in picked) + q.cost > budget:
                continue
            inspected += 1
            score, _ = _grade(gs, history + q.receipts)
            gain = score - current_value
            if gain > 0:
                candidates.append((-gain / q.cost, -gain, q.cost, q.name, q))
        if not candidates:
            break
        selected = min(candidates)[-1]
        picked += (selected,)
        remain.remove(selected)
        current_value, _ = _grade(gs, ini + tuple(w for q in picked for w in q.receipts))
    return _make_plan(gs, picked, ini, inspected, 0, False, 1 << len(qs))


def brute_force_oracle(goals: Iterable[Goal], queries: Iterable[Query], budget: int,
                      initial: Iterable[Witness] = ()) -> Plan:
    """Independent exhaustive oracle for test fixtures with at most 15 queries."""
    gs, qs, ini = _validate(goals, queries, budget, initial)
    if len(qs) > 15:
        raise ValueError("brute-force oracle limited to 15 queries")
    best = None
    examined = 0
    for size in range(len(qs) + 1):
        for candidate in combinations(qs, size):
            if sum(q.cost for q in candidate) > budget:
                continue
            examined += 1
            p = _make_plan(gs, candidate, ini, examined, 0, True, 1 << len(qs))
            if best is None or (-p.value, p.cost, p.selected) < (-best.value, best.cost, best.selected):
                best = p
    assert best is not None
    return best
