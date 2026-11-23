# Towards Adaptive Proof-Aware Agent Evaluation
## Technical manuscript outline and falsifiable study protocol — 2026-11-24

**Status:** Runnable method prototype and independently checkable synthetic experiments; **not submitted, not peer-reviewed, and not a claim of a novel POMDP solver**. Official task author status is independent.

### Abstract (method-note draft)

Tool-using agents can produce persuasive text that is not supported by the committed state of a service. Existing state-aware agent evaluations help close the gap between text and outcomes, but practical evaluation also faces history-dependent authorization, delayed evidence, contradictory receipts, and finite budgets for verifier-controlled queries. We introduce a research prototype combining (1) source-constrained, temporal proof obligations over service-owned facts, (2) whole-effect audit and explicit abstention on insufficient records, (3) conjunctive, positively scored task attainment, and (4) a finite-world exact Bayesian acquisition policy that selects read-only checks adaptively. A separately implemented exhaustive policy oracle validates the exact solver on 243 small scenarios. In 240 additional fixed-seed synthetic instances, adaptive acquisition beats an optimal precommitted query subset in eight and ties in 232, under the same prior and budget. Three engineered branch-identification examples attain expected utility 10 versus 5. All results are synthetic correctness and comparison checks, not external-agent performance or publication-level novelty evidence.

### 1. Scope and terminology

A **service receipt** is a typed record fetched over an independently controlled channel; an agent-authored JSON object is never evidence that the named service issued it. A **consequential effect** is a verified service-side mutation, not an LLM's claim of an action. A **proof obligation** for a task is a conjunction of typed predicates on issuer, subject, value, and effective time. An optional grant and revocation history determines whether a consequential effect is authorized.

A **certificate** is a deterministic set of linked record identifiers and hashes, useful for reproducibility, not a cryptographic signature or proof of omitted side effects. We require the host integration to enumerate all service-committed effects; otherwise coverage and success claims are conditional.

### 2. Active evidence acquisition

Let finite possible worlds be Ω = {ω_1,...,ω_n} with positive normalized prior p(ω). Each read-only query q has integer cost c(q)>0, an authenticated issuer/channel binding, and a deterministic typed response r(q,ω) in each world. A policy sees only the observed response sequence and can spend at most B, never querying the same source-operation twice.

A goal g = (O_g, v_g) is an obligation set O_g and nonnegative value v_g. Given collected observations E, the verifier's score is

    S(E) = Σ_g v_g · 1{every obligation in O_g has a non-conflicting
                        current authority-valid supporting receipt in E}.

The indicator requires a *conjunction* of all obligations, not any isolated positive keyword. The production verifier also audits all committed effects independently of goal score; empty effects cannot complete a goal merely by not violating a rule.

Define posterior p(ω | h) for history h by conditioning on the worlds with exactly the same authenticated observations. A finite-state Bellman rule computes expected goal reward:

    V(h,E,b,Q) = max(
        S(E),
        max_{q∈Q: c(q)≤b} Σ_o P(o|h,q) ·
            V(h+(q,o), E∪o, b-c(q), Q\{q})
    ).

A stop action is always present; when objective rewards tie, prefer lower *expected* query cost, then a deterministic lexical query name. A decision tree contains only response hashes and next queries; it does not expose latent world IDs to execution.

**Theorem 1 (conditional exactness).** For a finite, fully enumerated deterministic world-to-response model with positive priors, read-only non-repeating queries, positive costs, and score S above, the memoized policy returned by `solve_adaptive` maximizes the prior-expected verified-goal value subject to the exact pathwise budget B. Among equal-reward policies it minimizes expected query cost, with lexical tie-breaking.

**Proof sketch.** Induct on the number of affordable, not-yet-queried operations. With none available, stopping yields S(E) and zero additional cost. Otherwise every admissible policy either stops or chooses one q. The q response partitions the remaining worlds into observational equivalence classes; conditioning the prior on each class is Bayes' rule because responses are deterministic. By the induction hypothesis each continuation selected from the corresponding child state is optimal for its remaining budget. Weighting those child values by their exact posterior response probabilities yields the best value for q; taking the maximum over q and stop considers every admissible first decision. The secondary expected-cost and deterministic tie-break conditions are propagated over the same finite recursion. Each path spends only positive affordable query costs and removes the queried action, so termination and budget feasibility follow. □

**Theorem 2 (adaptivity dominance, conditional).** Under the same finite world model, budget, score, and prior, the optimal adaptive expected reward is at least that of the optimal fixed query subset. Proof: a fixed subset is a special case of an adaptive policy that ignores observations. This dominance does not imply an empirical advantage in a shifted real deployment.

### 3. Fair baselines and scientific evaluation

- **Fixed nonadaptive query set** (implemented): exhaustively enumerate all affordable subsets, choose maximum expected *goal* reward before observing anything; use identical prior, sources and budget to CAPE-Adapt.
- **Independent exhaustive adaptive policy oracle** (implemented): second recursion without the production memoization, limited to five worlds/probes; checks policy value and expected query cost. Additionally execute the learned policy in each hidden world and sum exact rational rewards.
- **CAPE-Plan v0.2** (implemented, NOT a fair online baseline): assumes the actual receipts before deciding which queries to execute, so can only be used as a clairvoyant full-information reference in appropriately designed comparisons.
- **Outcome-only record check** (implemented weak ablation): validates required expected values somewhere in an effect list but ignores issuer, permissions, missing side-effects, and stale records; useful to falsify a simplistic rule, not representative of prior SOTA.
- **External agent verifiers** (not run): real service-oriented and agent-state benchmark baselines must be evaluated under aligned interfaces and a disclosed, non-leaking task split. The literature includes Gaia2, AgentSuite and verifier auditing benchmarks; current prototype does not establish superiority to them.

Current committed evidence, rerunnable by `python run_all.py`:
1. 81/81 local framework unit tests and 97/97 earlier domain-specific tests;
2. 42 constructed invalid traces (36 rejected, six withheld) and three valid fixture references;
3. 363/363 exact v0.2 static scheduling cases (360 fixed seeds; 24 strict improvements over toy greedy, 336 ties);
4. 243/243 exact v0.3 adaptive cases (240 fixed seeds; 8 strictly outperform the optimum fixed subset, 232 ties);
5. three **deliberately designed** conditional branch cases with expected adaptive reward 10 and fixed 5;
6. GitHub Actions Python 3.11, 3.12, 3.13 replay is available in the public fork.

The 240 seeded cases are not human-curated held-out applications, and the 363 static cases have a different task model. Neither set supports significance claims about deployed agents. Do not pool distinct metrics as independent trials.

### 4. Decisive prospective tests for a competitive 2027/2028 method

**R1: Prior misspecification.** Freeze two or more priors before sampling a service trace. Perturb low-probability worlds, missing outcomes, and authorization revocations. Evaluate regret against the actual completion value, false-positive rate and abstention/coverage. This is the first research priority because Bayes-optimality under a wrong prior may be unsafe.

**R2: Service-committed traces.** Create a read-only connector over immutable service logs with independent issuer authentication and complete effect enumeration. Prohibit agent-visible access to hidden oracle state, task solutions, grader criteria, and model future outcomes.

**R3: Baseline parity.** Run identical external traces with equal token/tool/time budgets for fixed coverage, active myopic inspection, temporal authority-only verifier, state-only evaluator, and full CAPE. Report false accepts, false rejects, accepted coverage, calibration, completed task utility, end-to-end latency and overhead.

**R4: Leakage audit and preregistration.** Separate a design/dev split from externally curated frozen tasks. Pre-register failure modes, scoring thresholds, model versions, resets and evaluation budgets. Report failure cases, not only gains.

**R5: Contract synthesis as a new research hypothesis.** Learn minimal typed evidence obligations from observed service schemas and independently authenticated counterexamples; test whether this transfers to unseen tools without using gold grader data. This is not implemented yet and must be compared against existing active testing, POMDP planning and formal runtime verification work.

**R6: Proof-carrying RL as a new research hypothesis.** Only issue verified reward after trustworthy committed state and authorized goal proof. Train and test the resulting reward with confidence-aware abstention. Actual learned policy and nonstationary experiments are not implemented.

### 5. Fundamental limitations

The v0.3 DP model is finite, fully known, deterministic conditional on world, and read-only. The prior and tool response model are manually constructed. A source-labelled datum is not independently authenticated until the service adapter enforces that issuer boundary. The host must prove or assume effect-log completeness; CAPE cannot detect omitted effects from otherwise identical logs. Scaling is exponential in available queries and worlds. Bayes-optimal planning is not itself a new algorithmic paradigm.

These limitations define falsifiable work, not a reason to dismiss the implemented exact solver: it is a reproducible baseline and testbed for robust, trust-constrained extensions.

### Links

- [CAPE-Adapt implementation](../capegraph/adaptive.py)
- [Independent experiment](../experiments/adaptive_benchmark.py)
- [Method details](CAPE_ADAPT_METHOD.md)
- [CAPE-Plan static model](CAPE_PLAN_METHOD.md)
- [Gaia2](https://arxiv.org/abs/2602.11964)
- [AgentSuite](https://proceedings.mlr.press/v306/suh26a.html)
- [VerifierBench](https://arxiv.org/abs/2610.28679)
