"""CAPE-Contract: evidence-contract synthesis from independently labelled traces.

Finite candidate universe + CEGIS + exact minimum-cost hitting set. A verifier
must authenticate sources and audit complete effect logs *outside* this module.
No negative example is declared a proven policy violation by the synthesized
contract; an unsupported claim is UNVERIFIED, not automatically FAIL.

The counterexample oracle here is a *finite developer pool*; no general security
or OOD guarantee follows from passing it. No candidate is invented from hidden
world IDs, reference answers, or examples' labels: callers predeclare each
obligation from a documented, service-owned task schema.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .core import digest
from .planner import Need, Witness, _satisfies

MAX_ATOMS = 24
MAX_NEGATIVES = 512


@dataclass(frozen=True)
class Atom:
    name: str
    need: Need
    cost: int = 1

    def __post_init__(self) -> None:
        if not self.name or not isinstance(self.need, Need) or type(self.cost) is not int or self.cost <= 0:
            raise ValueError("atom requires a name, typed obligation, and positive integer cost")

    def as_dict(self) -> dict:
        n = self.need
        return {"name": self.name, "cost": self.cost, "token": n.token,
                "expected": n.expected, "issuers": list(n.issuers),
                "not_before": n.not_before, "not_after": n.not_after}


@dataclass(frozen=True)
class Trace:
    name: str
    receipts: tuple[Witness, ...]
    valid: bool

    def __post_init__(self) -> None:
        if not self.name or type(self.valid) is not bool or not isinstance(self.receipts, tuple):
            raise ValueError("trace must have unique-name candidate, tuple receipts, bool gold label")
        if any(not isinstance(x, Witness) for x in self.receipts):
            raise ValueError("receipts must be typed Witness records from a trusted test adapter")


@dataclass(frozen=True)
class Contract:
    atoms: tuple[Atom, ...]
    total_cost: int

    def __post_init__(self) -> None:
        if len({a.name for a in self.atoms}) != len(self.atoms) or sum(a.cost for a in self.atoms) != self.total_cost:
            raise ValueError("invalid contract cost or duplicate atom")

    def evaluate(self, receipts: Iterable[Witness]) -> str:
        """PASS only on positive evidence; otherwise withhold/UNVERIFIED."""
        evidence = tuple(receipts)
        return "PASS" if self.atoms and all(_satisfies(a.need, evidence) for a in self.atoms) else "UNVERIFIED"

    def with_effect_audit(self, receipts: Iterable[Witness], safety_verdict: str) -> str:
        """Cannot override missing/failed global service-side side-effect audit."""
        if safety_verdict not in ("PASS", "FAIL", "UNVERIFIED"):
            raise ValueError("expected typed CAPE safety verdict")
        if safety_verdict == "FAIL":
            return "FAIL"
        if safety_verdict == "UNVERIFIED":
            return "UNVERIFIED"
        return self.evaluate(receipts)

    def as_dict(self) -> dict:
        d = {"atoms": [a.as_dict() for a in self.atoms], "cost": self.total_cost,
             "decision_for_missing_evidence": "UNVERIFIED", "requires_effect_guard": True}
        d["sha256_without_digest"] = digest(d)
        return d


@dataclass(frozen=True)
class Certificate:
    status: str
    contract: Contract
    development_positives: tuple[str, ...]
    development_negatives: tuple[str, ...]
    counterexamples: tuple[str, ...]
    rejected_negatives: tuple[tuple[str, tuple[str, ...]], ...]
    oracle_calls: int
    states_visited: int
    indistinguishable: str | None

    def as_dict(self) -> dict:
        d = {"status": self.status, "contract": self.contract.as_dict(),
             "development_positives": list(self.development_positives),
             "development_negatives": list(self.development_negatives),
             "counterexamples": list(self.counterexamples),
             "rejected_negatives": [{"trace": n, "missing_obligations": list(m)}
                                    for n, m in self.rejected_negatives],
             "oracle_calls": self.oracle_calls, "states_visited": self.states_visited,
             "indistinguishable": self.indistinguishable}
        d["sha256_without_digest"] = digest(d)
        return d


def _screen(candidates: Sequence[Atom], positives: Sequence[Trace],
            negatives: Sequence[Trace]) -> tuple[tuple[Atom, ...], tuple[int, ...]]:
    compatible = tuple(a for a in candidates if all(_satisfies(a.need, p.receipts) for p in positives))
    # A single atom has a bit set if it withholds its evidence on that negative.
    coverage = tuple(sum(1 << j for j, n in enumerate(negatives)
                         if not _satisfies(a.need, n.receipts)) for a in compatible)
    return compatible, coverage


def _exact_hitting_set(atoms: tuple[Atom, ...], coverage: tuple[int, ...],
                       n_neg: int) -> tuple[tuple[Atom, ...] | None, int]:
    """Exact weighted hitting set, branch on the hardest uncovered counterexample.

    Objective (total cost, atom count, lexicographic atom names). The search
    explores choices covering the selected negative, so it cannot skip a
    feasible solution. A safe lower bound ignores interactions between covers.
    """
    if n_neg == 0:
        return (), 1
    full = (1 << n_neg) - 1
    for j in range(n_neg):
        if not any((c >> j) & 1 for c in coverage):
            return None, 0
    best: tuple[int, int, tuple[str, ...]] | None = None
    best_ids: tuple[int, ...] | None = None
    visits = 0

    def walk(covered: int, selected: int, spent: int):
        nonlocal best, best_ids, visits
        visits += 1
        ids = tuple(i for i in range(len(atoms)) if (selected >> i) & 1)
        if covered == full:
            metric = (spent, len(ids), tuple(atoms[i].name for i in ids))
            if best is None or metric < best:
                best, best_ids = metric, ids
            return
        if best is not None and spent >= best[0]:
            # costs are strictly positive: any further selected atom exceeds best.
            return
        missed = full & ~covered
        alternatives = []
        for j in range(n_neg):
            if not ((missed >> j) & 1):
                continue
            choices = tuple(i for i, mask in enumerate(coverage)
                            if (mask >> j) & 1 and not (selected >> i) & 1)
            alternatives.append((len(choices), j, choices))
        if not alternatives:
            return
        _, _, choices = min(alternatives, key=lambda x: (x[0], x[1]))
        for i in sorted(choices, key=lambda i: (atoms[i].cost / max(1, (coverage[i] & missed).bit_count()), atoms[i].name)):
            walk(covered | coverage[i], selected | (1 << i), spent + atoms[i].cost)

    walk(0, 0, 0)
    return (tuple(atoms[i] for i in best_ids) if best_ids is not None else None), visits


def greedy_contract(atoms: Iterable[Atom], positives: Iterable[Trace],
                    negatives: Iterable[Trace]) -> Contract | None:
    """Transparent greedy weighted set cover baseline, not a published SOTA."""
    candidate, pos, neg = _validate(atoms, positives, negatives)
    allowed, masks = _screen(candidate, pos, neg)
    uncovered = (1 << len(neg)) - 1
    chosen: list[Atom] = []
    while uncovered:
        opts = [(a.cost / max(1, (mask & uncovered).bit_count()), a.cost, a.name, i)
                for i, (a, mask) in enumerate(zip(allowed, masks)) if (mask & uncovered) != 0]
        if not opts:
            return None
        i = min(opts)[3]
        chosen.append(allowed[i]); uncovered &= ~masks[i]
    return Contract(tuple(sorted(chosen, key=lambda a: a.name)), sum(a.cost for a in chosen))


def _validate(atoms: Iterable[Atom], positives: Iterable[Trace],
              negatives: Iterable[Trace]) -> tuple[tuple[Atom, ...], tuple[Trace, ...], tuple[Trace, ...]]:
    candidate = tuple(sorted(atoms, key=lambda a: a.name))
    pos, neg = tuple(positives), tuple(negatives)
    if not 1 <= len(candidate) <= MAX_ATOMS or not pos or not neg or len(neg) > MAX_NEGATIVES:
        raise ValueError("1..24 atoms, >=1 positive, 1..512 negative traces required")
    if any(not isinstance(a, Atom) for a in candidate) or any(not isinstance(t, Trace) for t in pos + neg):
        raise TypeError("expected typed atoms and traces")
    if any(not t.valid for t in pos) or any(t.valid for t in neg):
        raise ValueError("only accepted traces in positives and rejected traces in negatives")
    if len({a.name for a in candidate}) != len(candidate):
        raise ValueError("duplicate atom names")
    if len({t.name for t in pos + neg}) != len(pos) + len(neg):
        raise ValueError("duplicate trace identities")
    # Positive/negative label contradictions cannot be reconciled by evidence.
    return candidate, pos, neg


def synthesize_contract(atoms: Iterable[Atom], positives: Iterable[Trace],
                        negatives: Iterable[Trace]) -> Certificate:
    """Counterexample-guided synthesis on *finite development* negative pool.

    The oracle inspects one development negative at a time. The frozen test
    pool must be disjoint and must never be passed here, even as metadata.
    """
    candidate, pos, neg = _validate(atoms, positives, negatives)
    allowed, all_masks = _screen(candidate, pos, neg)
    active: list[int] = []
    counterexamples: list[str] = []
    states = 0
    calls = 0
    while True:
        sub_masks = tuple(sum(1 << i for i, k in enumerate(active) if (mask >> k) & 1)
                          for mask in all_masks)
        selected, visited = _exact_hitting_set(allowed, sub_masks, len(active))
        states += visited
        if selected is None:
            negative = neg[active[-1]] if active else (neg[0] if neg else None)
            contract = Contract((), 0)
            return Certificate("UNIDENTIFIABLE", contract, tuple(t.name for t in pos),
                               tuple(n.name for n in neg), tuple(counterexamples), (),
                               calls, states, negative.name if negative else None)
        contract = Contract(selected, sum(a.cost for a in selected))
        calls += 1
        violating = next((j for j, t in enumerate(neg)
                          if contract.evaluate(t.receipts) == "PASS" or not selected), None)
        if violating is None:
            # Independently replay the separation certificate over every trace.
            rejections = tuple((t.name, tuple(a.name for a in selected
                                              if not _satisfies(a.need, t.receipts))) for t in neg)
            assert all(missing for _, missing in rejections)
            assert all(contract.evaluate(t.receipts) == "PASS" for t in pos)
            return Certificate("SEPARATED", contract, tuple(t.name for t in pos),
                               tuple(t.name for t in neg), tuple(counterexamples),
                               rejections, calls, states, None)
        if violating in active:
            raise AssertionError("the fitted contract accepted its own training counterexample")
        active.append(violating)
        counterexamples.append(neg[violating].name)


def independent_oracle(atoms: Iterable[Atom], positives: Iterable[Trace],
                       negatives: Iterable[Trace]) -> Contract | None:
    """Independent pure combinatorial enumeration (<= 16 atoms) for scientific tests."""
    from itertools import combinations
    candidate, pos, neg = _validate(atoms, positives, negatives)
    if len(candidate) > 16:
        raise ValueError("independent oracle limited to 16 candidates")
    permitted = [a for a in candidate if all(_satisfies(a.need, p.receipts) for p in pos)]
    best: Contract | None = None
    for k in range(len(permitted) + 1):
        for chosen in combinations(permitted, k):
            if not chosen:
                continue
            c = Contract(chosen, sum(a.cost for a in chosen))
            if any(c.evaluate(t.receipts) == "PASS" for t in neg):
                continue
            if best is None or (c.total_cost, len(c.atoms), tuple(a.name for a in c.atoms)) < \
               (best.total_cost, len(best.atoms), tuple(a.name for a in best.atoms)):
                best = c
    return best


def audit_frozen_split(contract: Contract, positives: Iterable[Trace],
                       negatives: Iterable[Trace]) -> dict:
    """Separate untouched test traces; this function does not update contract."""
    pos, neg = tuple(positives), tuple(negatives)
    if any(not x.valid for x in pos) or any(x.valid for x in neg):
        raise ValueError("invalid labels for frozen test set")
    accepted = sum(contract.evaluate(x.receipts) == "PASS" for x in pos)
    unsafe = sum(contract.evaluate(x.receipts) == "PASS" for x in neg)
    return {"valid_count": len(pos), "invalid_count": len(neg),
            "valid_accepted": accepted, "valid_withheld": len(pos) - accepted,
            "invalid_falsely_accepted": unsafe, "invalid_withheld": len(neg)-unsafe}
