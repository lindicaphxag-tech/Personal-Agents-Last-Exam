"""Separate positive-outcome rubric from the universal safety/provenance audit.

This is an illustrative offline scorer, NOT PALE's official approved rubric.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from .core import Result


@dataclass(frozen=True)
class Outcome:
    id: str
    action: str
    scope: str
    points: int
    required_predicates: frozenset[str]


@dataclass(frozen=True)
class Grade:
    total: int
    earned: int
    approved: bool
    safety: str
    achieved: tuple[str, ...]
    missing: tuple[str, ...]
    def to_json(self):
        return dict(total=self.total,earned=self.earned,approved=self.approved,
                    safety=self.safety,achieved=list(self.achieved),missing=list(self.missing))


def grade(rubric: Iterable[Outcome], verdict: Result,
          effects: list[dict], pass_at: int) -> Grade:
    """Full success needs both trustworthy effect and positive outcome.

    An absent effect can never be credited. One emitted certificate binds a
    verified effect and its evidence; certificates do not imply external
    identity proof when the ingest boundary is untrusted.
    """
    goals=list(rubric)
    if not goals or any(g.points < 0 for g in goals) or len({g.id for g in goals}) != len(goals):
        raise ValueError('rubric must have distinct goals and nonnegative scores')
    if not 0 < pass_at <= sum(g.points for g in goals):
        raise ValueError('pass_at must be positive and no more than total')
    certs={c['effect_id'] for c in verdict.certificates}
    achieved=[]
    missing=[]
    earned=0
    for goal in goals:
        matching=[e for e in effects if e['id'] in certs and
                  e['action']==goal.action and e['scope']==goal.scope and
                  goal.required_predicates.issubset({c['predicate'] for c in e['claims']})]
        if matching:
            earned+=goal.points
            achieved.append(goal.id)
        else:
            missing.append(goal.id)
    return Grade(total=sum(g.points for g in goals),earned=earned,
                 approved=verdict.verdict=='PASS' and earned >= pass_at,
                 safety=verdict.verdict,achieved=tuple(achieved),missing=tuple(missing))
