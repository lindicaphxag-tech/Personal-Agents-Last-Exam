# CAPE-Mix v0.5: certified randomization against globally fixed prior ambiguity

**Research method note — 2026-11-24.** Complete runnable CPU method prototype. This is *not* a new minimax theorem, not an external benchmark score, and not a declaration of academic coauthorship.

## Motivation: missing policies in CAPE-Robust v0.4

CAPE-Robust v0.4 enumerated every **deterministic** read-only verification decision tree under several candidate world priors, but optimized `max_{pure policy} min_{prior}`. It omitted a strategy class: policies that privately sample a random initial decision tree before collecting evidence.

When the uncertainty set is **globally coupled** (Nature selects one prior before the complete run) and Nature **does not observe** the sampled private random coin, the relevant game is `max_{distribution over policy trees} min_{prior} E[verified reward]`. This can strictly exceed v0.4.

If Nature observes the coin before choosing its prior, the original deterministic bound applies to each revealed tree and the gain can disappear. In security terms, private randomness is an **operational assumption**, never a property proved by source annotations alone.

## Method: exact two-prior convexification

Inputs are the same as v0.4: candidate latent worlds, service-bound observations, positive integer query costs, nonrepeating read-only queries, conjunctive authority-valid goal scoring, a hard *pathwise* query budget, and **two** candidate exact-rational priors. In the set of all admissible deterministic decision trees `π_i`, compute the two prior-expected rewards `(r_i1, r_i2)` and costs `(c_i1, c_i2)` by integrating every hidden world's deterministic trace, rather than choosing a worst-case prior separately in each observation branch.

For a mixed policy distribution `x` over trees, maximize

`V = max_{x_i >= 0, sum_i x_i = 1} min( sum_i x_i r_i1, sum_i x_i r_i2 )`.

The dual problem is

`U = min_{λ in [0,1]} max_i [λ r_i1 + (1-λ) r_i2]`.

Both are classical finite zero-sum matrix-game linear programs. Since Nature has only two pure prior scenarios, there is an optimal policy mixture supported on **at most two** deterministic trees. The code enumerates all pairs of nondominated trees from the global exact v0.4 search and all attainable endpoints and intersections between the two affine scenario-payoff lines. Every intersection, payoff, policy weight and dual bound is computed with `fractions.Fraction`; **no numerical tolerances** enter the runtime optimizer.

The dual certificate is derived by intersecting the linear constraints `λ r_i1 +(1-λ) r_i2 <= V` across **all retained nondominated trees**. The exact equality of primal reward and dual upper bound rules out an overlooked better mixture within this finite model. A separately coded SciPy HiGHS linear program in the optional test suite provides an independent *floating-point* check on 100 seeded games, but is never called by the production mixed policy solver.

### Theorems with conditions

**T1 (two-prior exactness).** Suppose (i) worlds and deterministic responses are completely enumerated, (ii) a prior is fixed before rollout and not chosen based on the private random seed, (iii) every query is read-only and source-authenticated by an independent adapter, and (iv) all feasible pure trees respect query budget `B` on every trajectory. Then `solve_mixed` computes a max-min-optimal randomized policy within the finite model, with support cardinality at most two. *Proof:* the pure-tree enumeration contains the finite strategy set; the linear program in `x` has two scenario reward constraints, so an extreme optimal feasible point has support at most two; pairwise affine-envelope maximization visits that point. The dual linear-constraint intersection verifies strong minimax duality by an exact rational certificate.

**T2 (strict gap to deterministic policies).** Two latent worlds `A` and `B`, two cost-one independent queries and a budget of one. Query A yields reward 10 only in world A; query B yields reward 10 only in world B. Priors are concentrated on A and B, respectively. Every deterministic policy has worst-case reward zero; a private fair-coin mixture yields expected reward 5 in each prior. In the *coin-revealed* variant Nature selects the losing world after observing the query and the guarantee returns to zero.

### Model restrictions

Exact enumeration is exponential in query/response histories and produces a Pareto frontier; the mixed solver caps eligible candidates at 1,400 and allows **exactly two** ambiguous prior scenarios. This restriction is checked explicitly rather than silently approximating a larger ambiguity set. The `max cost` secondary tie-break is the worst prior-expected query cost, but every deterministic component obeys the hard pathwise budget. A randomized mixed policy means *private pre-commitment to a whole valid tree*, not randomizing whether evidence counts as valid, changing authorization policy, or sampling source receipts.

## Results and reproduction

Run `python -m unittest discover -s tests -v`, `python experiments/mixed_benchmark.py`, then `python run_all.py`. Synthetic results are machine-readable in `experiments/mixed_results.json` with a reproducible content digest.

- **105/105** v0.5 framework unit tests (previous v0.4: 96), including 100 independently solved finite matrix games with SciPy HiGHS and 60 formerly frozen v0.4 full-policy tests.
- **180 unchanged fixed-seed random cases from v0.4**: mixed policy strictly increases worst-case score in **3**, ties in **177**. Sum of gain is `8727/560`, average `2909/33600` per case. These cases often have no provable positive goals, explaining low gain frequency. This is not a population success estimate.
- **240 deliberately conflict-enriched problems**: strict improvement in **180**, ties in **60**. This is a *stress test selected by construction* and cannot be used as an unbiased generalization metric.
- **One engineered globally coupled two-stage example**: exact randomized policy equals deterministic robust reward `9/2`; the absence of a randomization gain on this case is retained.
- **421/421 case-specific exact primal/dual certificates**, world-by-world replay and no prior switching within observations.
- **97/97 separately maintained PALE proposal-domain research regressions** continue to pass. These were never official PALE model-harness acceptances.

## 2026–2028 originality position and paper gates

- **2026 reproducible algorithmic contribution:** explicit evidence-query decision contracts, irreversible effect auditing, finite globally coupled prior ambiguity, private-coin randomized two-prior max-min policy and independently checkable exact certificates. Mathematical minimax and two-scenario support bounds are standard concepts; the work's research claim is their *verifier-integrated design, auditability and measured usefulness*.
- **2027 target:** learn or construct the world/prior ambiguity set from held-out logged service operations; test robust rewards against nonrectangular robust MDP and active evidence-acquisition baselines on identical source budgets. Do not conflate synthetic worlds with real service facts.
- **2028 target:** scalable column generation, unseen source schemas, outcome-verified agent reward and calibration under delayed/revoked authorization. These are research plans, not completed results.

Two specifically relevant prior foundations are 2026's *Non-Rectangular Average-Reward Robust MDPs* (arXiv:2603.00945) and 2025/2026 work on robust-MDP rectangularity and duality. These establish that globally coupled ambiguity and policy randomization already have substantive literature. A competitive publication requires head-to-head baselines and real externally sourced agent trajectories; the present synthetic study does not claim new mathematical foundations or SOTA.

## Trust and publication boundaries

A receipt labelled as coming from a service is not cryptographically authenticated merely by being in a local Python tuple. Real service adapters must bind channel identity and enumerate the complete committed effect log. The framework currently creates and queries *synthetic* world models; it cannot certify hidden production operations. Author-side implementation of an unpublished research design is not paper authorship in another group's work.
