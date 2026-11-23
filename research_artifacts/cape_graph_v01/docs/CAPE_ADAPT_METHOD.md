# CAPE-Adapt v0.3 — finite-belief, risk-aware read-only evidence acquisition

**Executed CPU research prototype, 2026-11-24; not an official PALE task or claimed frontier SOTA.**

## The v0.2 gap that motivated this method

CAPE-Plan v0.2 maximizes proof completion over queries with *hypothetical known receipts*. This models an oracle with access to future query outcomes; it is useful as a static full-information scheduling upper bound but is **not a real online decision policy**. CAPE-Adapt removes that clairvoyance: the auditor knows only a probability distribution over possible worlds and learns about the current world through read-only service queries.

## Formal model

- A finite latent world set \(\Omega\), with a positive normalized exact-rational prior \(P(\omega)\). A world determines the reply returned by each eligible read-only service query. The policy itself never receives the world label.
- A query \(q\) has a positive integer cost and a declared verifier-controlled service channel; a received reply is a finite set of typed observations `(token, value, issuer, time)`.
- An observation from `q` is accepted by the model only if its issuer agrees with the declared source channel. In a real integration, this must be independently authenticated by the service adapter; a source field self-asserted by a candidate agent is not proof.
- Each goal requires a conjunction of issuer- and time-valid facts. The latest valid observation controls each fact; contradictions at the same timestamp do not count as verified. The objective is the sum of values of **entirely proven goals**, not the number of retrieved facts.
- The policy may stop at any time. It cannot repeat a query and its total actual cost cannot exceed budget \(B\). Unknown outcomes get no fabricated success credit.

For belief \(b\), budget \(B\) and authenticated observations \(R\), a Bellman recurrence gives the Bayes-optimal expected reward:

\[
V(b,B,R)=\max\left(\mathrm{score}(R),\ \max_{q:c_q\le B}\sum_o P(o\mid b,q) V(b\mid o,B-c_q,R\cup o)\right).
\]

Two worlds that produce an identical reply are indistinguishable until further evidence arrives. The posterior is updated by *conditioning* the original world prior on the set of worlds consistent with the observed reply. The implementation stores a deterministic decision tree keyed by SHA-256 hashes of canonical typed observation sets, never by hidden world names. When two policies have identical expected completed-goal reward, it selects the policy with the lower expected query cost and deterministic lexical tie-breaking.

## Exactness and test design

`capegraph/adaptive.py` contains a memoized finite-belief dynamic program, and a **separately coded non-memoized exhaustive policy enumerator** used only for small test cases. `evaluate_fixed` is an independent, fair, non-adaptive baseline: it knows the *same distribution* over worlds, enumerates the affordable sets of queries, but must choose all queries before observing any outcome. It is not the clairvoyant v0.2 planner and not a claimed published competitive baseline. The script `experiments/adaptive_benchmark.py` additionally executes each policy against every enumerated hidden world and recomputes expected reward and cost from the world priors, confirming the DP report.

Exactness is guaranteed **only for the finite world model supplied by the experimenter**. Complexity remains exponential in queries/observation histories, so this prototype caps at 9 queries and 24 worlds. The study does not calibrate priors or predict online query latencies; the no-side-effect condition permits observations to be reordered without mutating world state.

## Reproduced synthetic experiment

```
python -m unittest discover -v -s tests
python experiments/adaptive_benchmark.py
```

Three hand-designed, different-domain conditional workflows use exactly two latent worlds and a two-query budget: a first observation distinguishes which branch matters, then the policy chooses the corresponding domain-specific proof query. A fixed plan has only one remaining slot and succeeds in half the worlds.

| Setting | Exact adaptive | Best fixed (same prior and budget) |
| --- | ---: | ---: |
| Domain-constructed release/authorization case | 10 | 5 |
| Domain-constructed lab/provenance case | 10 | 5 |
| Domain-constructed delivery/consent case | 10 | 5 |
| 240 seeded synthetic worlds, cases with strict adaptive benefit | 8 cases | 0 more than adaptive |
| 240 seeded synthetic worlds, tied | 232 | 232 |
| Independent exhaustive adaptive-oracle agreement | 243/243 cases | — |

The individual rows, rational expected values, expected query costs, state counts and exact prior metadata are in `experiments/adaptive_results.json`. The canonical JSON digest before the digest field is `a23d478985207b4022978f18ad4ef9de731cd95ce48e8b7c8a1e64c8728c4e0a`.

These are **developer-generated synthetic worlds**, not real user-agent trajectories, independent benchmark submissions or statistically representative deployments. The 3 manually constructed cases were specifically designed to exhibit an adaptivity gap; they are correctness witnesses, not an unbiased estimate of how frequently adaptive querying helps. No p-values or real-world task success rates are claimed.

## Next research gates for 2027–2028

1. **World misspecification / calibration:** allow abstention, interval probabilities or distributionally robust priors; compare regret against miscalibrated world ensembles and unseen source-policy changes.
2. **Active counterexample-guided contract synthesis (CECS):** learn a small candidate evidence-contract rule set from authenticated schemas and failures, then seek counterexamples without exposing hidden gold states to agents; preserve valid alternative workflows.
3. **External evaluation:** compare against verifier generation benchmarks such as VerifierBench and component audit suites such as AgentSuite with a deliberately published mapping of source-tool and task semantics; report false acceptance *and false rejection*, budget, runtime and authority violations. No direct external performance comparison has yet been run.
4. **Proof-carrying reward:** use real service commit receipts to issue typed evidence certificates and train a reward policy conditioned on positive verified outcomes and selective unknowns. Never transform a predicted receipt into a reward without a trusted service check.

**2026 deliverable:** complete runnable proof-of-concept of finite-belief adaptive evidence acquisition and exhaustive small-model validation. **2027/2028 objectives:** robust priors, contract synthesis and proof-aware training are future research targets; their results have not been obtained.
