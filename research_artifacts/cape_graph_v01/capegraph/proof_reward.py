"""PCR: proof-carrying rewards from independently replayable verification.

No actual RL training, model evaluation, cryptographic issuer attestation or
PALE official rubric is claimed. The value may be positive ONLY for verified
positive effects, and failed/unknown prefixes withdraw provisional credit.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from .core import Verifier, digest
from .scoring import Outcome, grade


@dataclass(frozen=True)
class RewardRecord:
    step: int
    verdict: str
    earned: int
    total: int
    credited: float
    delta: float
    proof_digest: str
    evidence_digest: str
    certified_effects: tuple[str,...]

    def to_json(self):
        return dict(step=self.step,verdict=self.verdict,earned=self.earned,
                    total=self.total,credited=self.credited,delta=self.delta,
                    proof_digest=self.proof_digest,evidence_digest=self.evidence_digest,
                    certified_effects=list(self.certified_effects))


@dataclass(frozen=True)
class RewardTrace:
    run_id: str
    policy_digest: str
    records: tuple[RewardRecord,...]
    final_reward: float
    trace_digest: str

    def to_json(self):
        return dict(run_id=self.run_id,policy_digest=self.policy_digest,
                    records=[x.to_json() for x in self.records],
                    final_reward=self.final_reward,trace_digest=self.trace_digest)


def _policy_fingerprint(engine: Verifier, rubric: tuple[Outcome,...], threshold:int) -> str:
    data={'rules':[dict(action=k,required=[list(x) for x in v.required],
                        allowed=sorted(v.allowed),unique=v.unique,
                        scope_bound=sorted(v.scope_bound),
                        required_ancestry=[list(x) for x in v.required_ancestry])
                   for k,v in sorted(engine.rules.items())],
          'issuers':{k:sorted(x) for k,x in sorted(engine.fact_issuers.items())},
          'grants':sorted(engine.grant_issuers),
          'goals':[dict(id=g.id,action=g.action,scope=g.scope,points=g.points,
                        required_predicates=sorted(g.required_predicates)) for g in rubric],
          'pass_at':threshold}
    return digest(data)


def replay_reward(engine: Verifier, rubric: Iterable[Outcome], trusted_log:list[dict],
                  effect_log:list[dict], pass_at:int, run_id:str='synthetic_run') -> RewardTrace:
    goals=tuple(rubric)
    if not isinstance(run_id,str) or not run_id or len(run_id)>160:
        raise ValueError('run_id required')
    # Validates goal uniqueness and score range even for the empty prefix.
    goal_total=sum(g.points for g in goals)
    empty_grade=grade(goals,engine.evaluate(trusted_log,[]),[],pass_at)
    del empty_grade
    policy_hash=_policy_fingerprint(engine,goals,pass_at)
    records=[];old_credit=0.0
    for count in range(len(effect_log)+1):
        prefix=effect_log[:count]
        result=engine.evaluate(trusted_log,prefix)
        outcome=grade(goals,result,prefix,pass_at)
        # Strict positive reward only for wholly verified prefix. One unknown
        # or violated contract invalidates prior provisional credit.
        credit=round(outcome.earned/goal_total,12) if result.verdict=='PASS' else 0.0
        delta=round(credit-old_credit,12)
        old_credit=credit
        certs=tuple(x['effect_id'] for x in result.certificates)
        evidence={'trusted_log':trusted_log,'effect_log':prefix}
        proof={'policy_digest':policy_hash,'verdict':result.verdict,
               'outcome':outcome.to_json(),'certificates':list(result.certificates)}
        records.append(RewardRecord(count,result.verdict,outcome.earned,goal_total,
                                    credit,delta,digest(proof),digest(evidence),certs))
    base=dict(run_id=run_id,policy_digest=policy_hash,
              records=[x.to_json() for x in records],final_reward=records[-1].credited)
    return RewardTrace(run_id,policy_hash,tuple(records),records[-1].credited,digest(base))


def verify_reward_trace(asserted:RewardTrace,engine:Verifier,rubric:Iterable[Outcome],
                        trusted_log:list[dict],effect_log:list[dict],pass_at:int) -> bool:
    """Independent recomputation, not mere trust in a supplied SHA256 string."""
    try:
        actual=replay_reward(engine,rubric,trusted_log,effect_log,pass_at,asserted.run_id)
    except (ValueError,KeyError,TypeError):
        return False
    return asserted == actual


def reward_for_training(record:RewardRecord) -> float:
    """No positive learning reward from FAILED or UNVERIFIED prefixes.

    The signed delta may be negative after later invalidation; callers using
    full trajectory return must preserve this withdrawal, not clip it to zero.
    """
    if record.verdict!='PASS':return min(0.0,record.delta)
    return record.delta
