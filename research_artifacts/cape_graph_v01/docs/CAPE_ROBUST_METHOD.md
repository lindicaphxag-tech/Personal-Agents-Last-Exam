# CAPE-Robust v0.4 — globally coupled prior-robust evidence acquisition

**Research note, 24 November 2026.** Implemented in Python 3.11+ with exact rational arithmetic, deterministic finite policy trees and full CPU regression tests. This is **not an original robust POMDP theory claim**, an approved PALE task, or an external agent benchmark score. Prior uncertainty is a studied subject in robust MDPs/POMDPs; the domain-specific research hypothesis here is its coupling to issuer/temporal/authority-constrained evidence obligations.

## Why this extension matters

CAPE-Adapt v0.3 solves Bayes-optimal evidence acquisition under a **single exact prior** over a fully enumerated finite world set. A verifier often has an incorrect estimate of which authorized historical event, tool state, and witness is likely. A strategy optimized only for that prior may query a high-value but narrow proof and lose nearly all value when the prior shifts.

CAPE-Robust accepts a *fixed set of candidate world priors* `Prior(name, probabilities)` as an ambiguity set. The policy selects its query based on authenticated observations and is optimized for the **smallest expected fully verified task reward over this set**. The adversary must choose **one prior for the entire episode**; an algorithm that independently substitutes different priors in different observation branches solves a different, rectangularized and potentially too pessimistic problem.

## Objective and semantics

Worlds \(\omega_1,\ldots,\omega_n\) produce deterministic replies to a small collection of read-only verifier-controlled queries \(q\). Queries have positive integer cost \(c_q\), and an adaptive deterministic policy \(\pi\) may select queries sequentially, observing only the actual service response. Every rollout has accumulated query cost \(C_\pi(\omega)\le B\). The issued receipts must be verified by the trusted service adapter before being used for authorizations or reward.

Given a set of signed-off, conjunctive proof goals with domain-specific issuer, value and time requirements, a deterministic score \(R_\pi(\omega)\) is computed from the observed proof witnesses. A verifier may withhold credit if a necessary witness is absent, contradicted, stale or untrusted. A non-action never earns a fictitious positive task result.

For normalized nonnegative prior vectors \(p_j=(p_{j1},...,p_{jn})\), \(j=1,...,k\), CAPE-Robust solves **over deterministic policies**:

\[
\pi^* \in \arg\max_\pi \min_{j=1}^k \sum_{i=1}^n p_{ji} R_\pi(\omega_i),
\qquad \forall i:\ C_\pi(\omega_i)\le B.
\]

Secondary objective: minimize \(\max_j \sum_i p_{ji}C_\pi(\omega_i)\). Final tie is a deterministic lexical tree key. It is a **static, globally coupled prior ambiguity** objective. The solver is not allowed to reassign the chosen prior after an observation. Every prior in the convex hull of the supplied vectors is covered because expected score is affine in the prior and the minimum over that hull is at a supplied extreme.

This maximizes **minimum expected nonnegative proof completion**, NOT real-world safety or the probability of no unauthorized state changes. The independent CAPE-Graph verifier still owns correctness/authorization checks. Predicted receipts from an untrusted LLM remain unusable as evidence.

## Exact finite algorithm

A policy is represented by a finite tree: an internal node selects a verifier-controlled query and a child is chosen by a canonical hash of the authenticated response. At each subproblem, compute candidate *per-world* reward/cost vectors for feasible continuation trees, including the option to stop. For a query, group observationally indistinguishable worlds, recursively enumerate child policies and take the Cartesian product over their branches. A query's cost is added to each world's path cost. This global per-world representation preserves the correlation induced by choosing one fixed prior across every branch.

The algorithm removes an option \(b\) if another option \(a\) satisfies **for every possible world**:

\[
R_a(\omega)\ge R_b(\omega), \qquad C_a(\omega)\le C_b(\omega).
\]

Why this is safe: any nonnegative normalized prior maps these componentwise inequalities to weakly larger expected reward and weakly smaller expected cost. Thus no prior scenario can prefer the dominated candidate under the stated max-min/secondary objective. Applying this elimination at a child branch is also safe: replacing the dominated child cannot reduce the parent reward vector or increase its cost vector. Induction on remaining affordable queries shows that keeping only nondominated candidates preserves the optimum. When two vectors are equal, retaining one canonical representative can change only an arbitrary lexical tie, not value/cost optimality.

**Theorem (conditional exactness).** For the finite deterministic world-response table, authenticated service-channel model, positive integer probe costs, read-only nonrepeating queries, exact prior vectors, and a goal score determined solely by observed witnesses, the algorithm returns the optimal deterministic policy for the globally fixed-prior max-min objective and the stated secondary cost objective. **Proof:** exhaustive induction over query trees, with the componentwise replacement/dominance argument above. An independently written *non-memoized, non-Pareto-pruned* exhaustive decision-tree oracle verifies the numerical result on small cases.

**Limit:** Mixed/randomized policies may achieve larger max-min reward; no claim of optimality among stochastic strategies is made. Exact search remains exponential/superexponential and is capped at 6 queries, 6 worlds, 12 prior scenarios and a bounded Pareto frontier; exceeding the limit raises an error instead of silently returning an approximate optimum.

## Reproducible experiments

```bash
python -m unittest discover -v -s tests
python experiments/robust_benchmark.py
python run_all.py
```

### Prior reversal (constructed counterexample)

Two worlds A/B and two 1-cost queries. The narrow query reveals a proof worth 10 only in world A; the broad query returns an independently valid proof worth 6 in both. The nominal prior is (0.9,0.1), and the shifted prior is (0.1,0.9).

- Nominal-only optimal query: narrow; nominal expected score 9, **minimum over both priors 1**.
- Robust optimal query: broad; score **6 under both priors**.
- This constructed improvement is not an estimate of average performance on real users.

### Coupled-ambiguity demonstration (constructed counterexample)

Four possible worlds: A-good, A-bad, B-good, B-bad; one branch-identifying query costs 1 and the two branch-specific verification queries cost 2. Budget 3. Two global priors have opposite branch-success correlations. CAPE-Robust chooses the branch-identifying query, follows the relevant branch, and obtains expected verified score **9/2 under both fixed priors**. Any fixed subset has maximum minimum expected score **1/2**. A procedurally invalid calculation selecting the unfavourable prior independently in the A and B branches could report an artificial lower value of **1** on that particular policy; our solver does not permit such scenario switching.

### Frozen synthetic seed panel (not a public benchmark)

- **180** seeded random cases, each containing 2–3 worlds, 2–4 read-only queries and a pair of contrasting priors; **all 180** independently match a second exhaustive decision-tree oracle.
- Combined with the four constructed cases: **184/184** exact oracle agreements.
- Robust policy beats the nominal-only policy on the **minimum expected reward over the two supplied priors** in **1/180** random cases and ties in **179/180**. No case loses on the stated objective (by optimization definition).
- Compared with the **optimal robust fixed query subset**, adaptive robust querying is strictly better in **12/180** and ties in **168/180**.
- Additional post hoc *out-of-set* prior stress: robust policy beats nominal in **1/180**, loses in **1/180**, ties in **178/180**. There is **no formal guarantee** when deployment probabilities lie outside the modelled ambiguity set.
- Raw rows, exact rational fractions, per-case query names/costs and digests are in `experiments/robust_results.json`. Frozen SHA-256 of canonical content before embedding digest: `04f238caf8df9740ba51ef72ed9be7e9b3ec5cd0171f50586a73d56d6c7c9b1b`.

**All random cases were generated from programmatic distributions defined alongside the model under development. They are not externally curated held-out agent tasks, and the counts are not confidence intervals, SOTA comparisons or empirical patient/industry results.** The constructed examples deliberately make the targeted failure modes visible.

## What 2027–2028 work must establish

1. **Prior-set calibration:** learn valid ambiguity sets from held-out authenticated tool histories; compare out-of-set regret, rewards, failure coverage and calibration against nominal Bayes, fixed plan, robust rectangular and robust globally coupled baselines.
2. **Scalable algorithm:** test branch-price dual decomposition, certified upper/lower bounds and anytime early stopping on hundreds of worlds instead of <=6. Report deterministic correctness tolerances, budgets, and worst-case time/memory.
3. **Complete externally issued evidence:** use actual service-side logs, authorization/revocation and idempotency records. Track false acceptance *and* false rejection rather than treating score as safety.
4. **New contract synthesis:** induce minimal verifiable obligations from authenticated event schemas and independently obtained counterexamples; preserve semantically equivalent legitimate workflows.
5. **Proof-carrying reward:** compare reinforcement learning with authenticated positive outcome certificates, model prediction-only rewards, and ungrounded transcript graders on equal budgets; no success claim until the learned policy is actually evaluated.

## Relationship to prior work

Distributionally robust MDPs/POMDPs and nonrectangular uncertainty sets are **existing research areas**. Relevant work includes [Policy Gradient Algorithms for Robust MDPs with Non-Rectangular Uncertainty Sets](https://arxiv.org/abs/2305.19004), [Distributionally Robust Partially Observable Markov Decision Process with Moment-based Ambiguity](https://arxiv.org/abs/1906.05988), and [Rectangularity and Duality of Distributionally Robust Markov Decision Processes](https://doi.org/10.1007/s10107-025-02297-y). The four evidence-specific subproblems (authentic issuer, temporal authority, full effect enumeration, conjunctive task proof) and the correctness implications of **globally coupled prior uncertainty** are the proposed *integration/research direction*, not a verified claim to have invented robust planning. There is no external publication acceptance, no PALE task merge, and no ALE task acceptance at this stage.
