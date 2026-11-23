"""CAPE-Graph research prototype; not an official PALE verifier."""
from .core import Rule, Finding, Result, Verifier, digest, minimize_witness
from .scoring import Outcome, Grade, grade

__all__ = ["Rule", "Finding", "Result", "Verifier", "digest", "minimize_witness", "Outcome", "Grade", "grade"]

from .planner import Need, Goal, Witness, Query, Plan, solve_exact, greedy_marginal
__all__ += ["Need", "Goal", "Witness", "Query", "Plan", "solve_exact", "greedy_marginal"]

from .adaptive import Probe, World, Decision, AdaptivePolicy, solve_adaptive, evaluate_fixed
__all__ += ["Probe", "World", "Decision", "AdaptivePolicy", "solve_adaptive", "evaluate_fixed"]

# Research-only exact robust optimizer (fixed prior ambiguity; deterministic policies).
from .robust import Prior, RobustDecision, RobustPolicy, solve_robust

from .mixed import MixSupport, MixedPolicy, solve_mixed
__all__ += ["MixSupport", "MixedPolicy", "solve_mixed"]

# CAPE-Contract v0.6: finite-pool CEGIS evidence obligations.
from .contracts import Atom, Trace, Contract, Certificate, synthesize_contract, greedy_contract, independent_oracle, audit_frozen_split
__all__ += ["Atom", "Trace", "Contract", "Certificate", "synthesize_contract", "greedy_contract", "independent_oracle", "audit_frozen_split"]
