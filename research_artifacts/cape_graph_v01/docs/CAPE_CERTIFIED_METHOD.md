# CAPE-Certified v0.7: certified robust evidence acquisition on observation DAGs

## Problem and scope

A finite world set W specifies deterministic, source-bound receipts for every available read-only probe. Every probe is usable at most once; its positive integral cost counts toward a pathwise budget B. A verified-goal reward R(h) is computed from accumulated receipts, including time and conflicting evidence checks. Nature selects one of m priors before observing private policy randomness; the objective is max_pi min_j E_{w~p_j,pi} R(h_terminal). The same prior governs the entire trajectory. All modeled worlds are retained even when their mass under one prior is zero. A prior family is not a claim about real deployment calibration.

## Contribution A: shared-state exact pricing and anytime certificates

Compile histories into a DAG keyed by remaining probes, compatible worlds, remaining budget, and canonical accumulated receipts. At each node s, a probe partitions compatible worlds into distinct observation children. For a rational world weight vector u, compute the unnormalized Bellman recurrence

    V(s) = max(R(s) sum_{w in W_s} u_w, max_a sum_{t in children(s,a)} V(t)).

Integer scaling by the common denominator makes every calculation exact. The state includes all information needed for admissibility, transition and reward, so backward induction proves this is a best response over all contingent pure strategies. No division by posterior mass is needed.

A restricted payoff-matrix LP proposes primal policy mixtures and dual prior mixtures. Rationalize each to a valid simplex, replay pure support policies independently across all worlds, and compute lower bound L as their worst prior reward. With dual prior weights y, exact pricing on u = sum_j y_j p_j gives upper bound U. Weak duality ensures L <= V* <= U for every valid mixture, irrespective of LP numerical accuracy. Preserve the best L and U across iterations; a nonzero gap is reported explicitly, not rounded away. Finite strategy generation is not a polynomial-time guarantee.

## Contribution B: sparse realization-flow formulation

Use nonnegative variables x_{s,a} for stop or probe choices. Let r be the root. The constraints are

    sum_a x_{s,a} = 1[s=r] + sum_{(p,b):s in children(p,b)} x_{p,b},
    z <= sum_s x_{s,stop} R(s) sum_{w in W_s} p_j(w)  for every j.

Maximize z. Unlike a conventional stochastic transition matrix, a queried action broadcasts realization mass to every *compatible observation branch*. Each fixed world chooses exactly one such child; mass is not divided by the number of outcomes. This is conditional-on-world realization probability, not unconditional probability across the whole DAG.

**Exact formulation argument.** Given any history-dependent randomized policy with randomness independent of the world, all worlds consistent with a particular history induce identical action/receipt traces there, so that history's realization mass is common to those worlds. Histories merged into s have the same compatible world set and sufficient state for future reward and actions. Summing their action realization masses satisfies the flow constraints and preserves every world's expected terminal reward. Conversely, for any feasible flow, take action a at s with probability x_{s,a}/sum_b x_{s,b} (stop at unreachable states). Induction in topological order yields the specified conditional-on-world arrival masses; in each world there is exactly one compatible observation child per chosen query. Thus the behavioral policy preserves the LP's per-world rewards and respects the pathwise budget by construction. Consequently the exact-arithmetic LP and the original finite robust randomized problem have the same optimal value under the stated assumptions.

The sparse matrix uses one variable per legal node-action pair plus z, one equality per node and one inequality per prior. DAG compilation can still grow exponentially with probes; no polynomial bound in the original input is claimed. The implementation is capped at 9 probes, 24 worlds, 64 priors and 100000 DAG nodes by default. SciPy/HiGHS generates candidate solutions. Exact rational per-world behavioral replay computes L, exact Bellman pricing computes U; the independent verifier recomputes both rather than trusting floating objectives. Zero gap means exact optimality within this model. If rationalization loses accuracy, the nonzero certified gap remains valid. Expected costs are reported, not secondarily optimized by the flow LP.

## Contribution C: executable observation-only policy

`execute_flow` selects actions with private rational randomization and accepts only a read-only probe callback; the executor receives no world identifier. It checks witness issuer/response membership, duplicate receipts, budget and probe reuse. An unknown observation or adapter failure produces UNVERIFIED with no positive reward. Service signature authentication and actual authorization are the caller's responsibility; this prototype does not authenticate a service merely because a witness issuer field matches. Verify the certificate on the intended model before running. It does not implement re-planning under out-of-model stochastic receipts.

## Reproducible evaluation (CPU)

- 120 seeded small synthetic cases, comparison against an enumerated policy payoff LP, 120/120 zero gaps for both new solvers.
- Six designed scaling cases, each with a separately constructed fixed-query mixture LP reference. At 24 worlds, 24 priors and 9 probes, optimal randomized adaptive reward 5 versus fixed-query mixture 1.25. 149 DAG nodes, 271 LP variables, 4096 maximal tag-conditioned policies; column generation uses 58 columns. The constructed case demonstrates an adaptivity separation, not a general performance ratio.
- Seven alternating end-to-end solves of that same 24-world case, excluding warm-up: median column generation 0.938353488 s, sparse flow 0.021975607 s (42.70x). Includes compilation and certificate calculation, not separately rerunning verifier. Small cases do not show a universal speedup; timings are machine-dependent.
- 17 additional test methods, including 40 no-pruning exact pricing checks, 50 no-pruning full-policy LP comparisons, 24 two-prior compatibility checks, certificate mutation, zero-mass worlds, stale/conflicting receipts, capped nonzero-gap results and 128 observation-only simulated replays. Full framework suite 134 tests; separate earlier domain suite 97 tests. No external agent rollouts, benchmark acceptance, upstream merge or author qualification is established by these tests.

## Literature positioning and limits

Related foundations include sequence-form/realization-plan LPs, double-oracle strategy generation, robust POMDPs and multi-environment POMDPs. The proposed research contribution is the evidence-contract-specific observation DAG and auditable realization-flow implementation with independently checked rational certificates, not invention of LP, Bellman recursion or mixed strategies. A top-tier claim requires comparisons to general sequence-form or robust POMDP solvers, real evidence-acquisition tasks and calibrated prior ensembles, larger-scale profiling, and independent peer review. Global prior ambiguity, deterministic read-only observations and finite pathwise budgets are essential assumptions here. The theoretical argument is for this restricted model only.

## Reproduce

    python -m pip install -r requirements-v07.txt
    python -m unittest discover -v -s tests
    python experiments/certified_benchmark.py
    python experiments/certified_timing.py
    (cd prior_97 && python verify_all.py)

The frozen result JSON is deterministic apart from the separately stored machine-dependent timing measurements. The older methods and tests are retained for regression comparison.
