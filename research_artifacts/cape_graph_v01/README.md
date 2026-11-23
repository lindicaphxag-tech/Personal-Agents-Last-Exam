# CAPE-Contract v0.6 — Counterexample-guided evidence contract synthesis

**Executed CPU research prototype, 2026-11-24.** No official PALE task approval or paper author claim. Full chain: CAPE-Graph → Plan → Adapt → Robust → Mix → Contract.

## New in v0.6

`capegraph/contracts.py` synthesizes a minimum-cost **positive proof-obligation conjunction** from task-owner-approved evidence atoms and labeled development traces. A finite CEGIS loop refines the rule with negative counterexamples; the exact weighted hitting-set solver has an independently coded exhaustive reference. The output includes a certificate identifying which obligation each negative fails and a reproducible canonical digest. If available evidence cannot separate two different outcomes, it returns `UNIDENTIFIABLE`; missing proof returns `UNVERIFIED`, not invented `FAIL`.

- **117/117 framework tests**, including 210 random weighted-hitting-set cases checked against independent full enumeration, plus **97/97 previous PALE-domain CPU regressions** = **214 separately counted unit tests**.
- Three synthetic service domains: 18 valid / 60 invalid **development** examples; 405 valid / 450 invalid independent-seed **frozen synthetic** examples. Of 405 valid, 45 newly authorized issuer-migration cases are withheld under the old schema; 90 invalid traces with unauthorized committed effects are **falsely accepted by the evidence-only contract** even though they are blocked when composed with the separate full-effect verifier. These are deliberately constructed failure modes, not field reliability rates.
- An engineered weighted-cover case shows exact minimum **2 rule atoms** vs **3 atoms** for our transparent greedy implementation. Known weighted hitting set and CEGIS are prior art, not uniquely novel algorithms.
- Zero GPUs or paid APIs: `python -m unittest discover -s tests -v` and `python experiments/contract_benchmark.py` reproduce the artifacts.

**Read:** [`docs/CAPE_CONTRACT_METHOD.md`](docs/CAPE_CONTRACT_METHOD.md) for formal definitions, conditional exactness proof, trust assumptions, counterexamples and falsifiable research roadmap.

---

# CAPE-Graph v0.5 — Proof-grounded adaptive evaluation and exact robust mixed policies

**Research prototype, dated 2026-11-24** · Python 3.11+ standard library · CPU · zero paid APIs · author-side evidence for three unapproved PALE Task proposals.

**Goal:** Assess *all consequential committed actions* using time-indexed, issuer-bound evidence, scoped permissions and a separate positive-outcome rubric. A correct answer string or a signed agent-written trace is not evidence of a real service-side action.



## New in v0.5 — CAPE-Mix, exact globally coupled two-prior randomization

**Executed 2026-11-24 (CPU)**. `capegraph/mixed.py` corrects an important strategy-class limitation of v0.4: under two globally fixed possible prior distributions and a **private** pre-query random seed, randomly mixing two evidence-query decision trees can strictly increase worst-case verified task reward. The runtime solver uses exact-rational two-scenario minimax geometry with a separately verified primal/dual certificate; *the matrix-game mathematics is established prior art*, not presented as a new theorem. It preserves all earlier issuer, time, authorization and whole-goal evidence contracts.

- **105 framework unit tests** plus **97 earlier domain-task regression tests**: **202 tests** (independent scopes).
- **421/421 exact two-prior policy-value/primal–dual certificates**: 180 frozen unfiltered v0.4 scenarios, 240 *deliberately constructed* prior-conflict stress cases, one nonrectangular two-stage control.
- Original 180: **3 strict randomized gains**, **177 ties**; 240 intentionally conflict-enriched: **180 gains, 60 ties**. The latter is *not a population frequency estimate*. No agent-model benchmark performance has been measured.
- One clean witness: deterministic max-min reward **0**, private 50/50 policy **5**, while **seed-revealed** randomization returns the guarantee to **0**.
- Optional independently implemented SciPy HiGHS reference validates 100 separate small games; **SciPy is used only in testing**, not the exact runtime solver.

Read [`docs/CAPE_MIX_METHOD.md`](docs/CAPE_MIX_METHOD.md) for exact assumptions, proofs, costs, alternative strategies and 2027–28 research gaps; run `python experiments/mixed_benchmark.py` for all cases. Public CI checks reproducible source and output across Python 3.11–3.13.

## New in v0.3 — CAPE-Adapt, uncertainty-aware active checking

The previous v0.2 planner optimizes using **hypothetical known query returns**, and should be interpreted as a full-information upper bound rather than a deployable online strategy. `capegraph/adaptive.py` now implements **exact finite-belief adaptive evidence acquisition**: a distribution of possible source-authenticated worlds, an observation-conditioned posterior, and a decision tree selecting which read-only evidence to query next. This is a bounded Bayes-optimal policy *under the specified prior*, not learned from real agents.

- **81/81** framework CPU tests, plus the separate original **97** task-specific research tests.
- **243/243** adaptive synthetic problems matched an independently coded non-memoized exhaustive policy oracle; the policy's expected value/cost was independently replayed world by world.
- Three constructed cases give expected objective **10 vs 5** against the fair best fixed query plan. For **240** separate random synthetic latent-world problems, adaptive is strictly better on 8 and tied on 232; neither is a statistically representative real-task result.
- Three-version reproducibility workflow is part of the public research branch. Exact method and prior assumptions: [`docs/CAPE_ADAPT_METHOD.md`](docs/CAPE_ADAPT_METHOD.md).

## New in v0.2 — CAPE-Plan (exact evidence acquisition)

The new `capegraph/planner.py` implements **budgeted read-only evidence acquisition** for conjunctive outcome goals. It selects query subsets subject to costs, trusted issuer constraints, time windows, current-state conflict resolution and a hard budget. Exact branch-and-bound (up to 20 queries) is independently checked against an exhaustive subset oracle; a simple greedy-marginal baseline is reported separately. This is a new algorithm component of this research artifact, not evidence of publication-level novelty or a real-world SOTA result.

- **71/71** CPU regression tests (59 original + 12 new planner tests).
- **363/363** independent brute-force checks on three designed proof-conjunction cases and 360 fixed-seed synthetic query worlds.
- Over 360 seeded synthetic worlds, exact planning outperforms the transparent greedy baseline on 24, ties on 336, and is worse on 0; summed verified-goal value is **3,670 vs 3,408**. These values cannot be generalized to real tasks or model agents.
- `python experiments/planner_benchmark.py
python experiments/adaptive_benchmark.py` reproduces all individual rows and their canonical digest. For semantics and limitations, see [`docs/CAPE_PLAN_METHOD.md`](docs/CAPE_PLAN_METHOD.md).

### Quick start

```bash
python -m unittest discover -v -s tests
python experiments/ablation.py
python experiments/planner_benchmark.py
python -m capegraph --case release --json
python -m capegraph --case notice_restrictive
python -m capegraph --case notice_permissive
```

**Current local result:** 59/59 original framework unit tests (plus 12/12 new evidence-planner tests). Three synthetic positive references PASS; 42 deliberately invalid cases are not accepted (36 `FAIL`, 6 `UNVERIFIED`). A transparent weak *outcome-only* baseline accepts 36/42 invalid examples. The baseline is **our own toy ablation**, not another published system. The same world facts with only the earlier public-notice authorization changed flip `FAIL` -> `PASS`. These are author-side deterministic experiments—not model-agent rollouts, generalizable reliability estimates, PALE merge, or authorship confirmation.

### What's inside

| Module | Purpose |
| --- | --- |
| `capegraph/core.py` | DAG provenance, issuer whitelist, time-bound permissions, revocations, stale/contradictory facts, complete effect audits, three-valued verdicts and proof-linked fingerprints |
| `capegraph/adaptive.py` | Exact discrete-belief adaptive query planning with per-observation posterior updates and independent exhaustive oracle |
| `capegraph/planner.py` | Exact budgeted evidence acquisition with timestamped issuer claims and conjunctive proof goals |
| `capegraph/ingest.py` | Accept only pre-authorized *verifier-controlled* service channels; issuer identity is assigned by the controlled channel, not copied from an agent's JSON |
| `capegraph/scoring.py` | Independent positive outcome evidence; no-op receives 0 points even when the safety audit finds no violation |
| `capegraph/fixtures.py` | Synthetic release/credit, scientific CPU protocol and step-free item dispatch; includes a prior-history authorization counterfactual |
| `tests/` | 71 deterministic CPU tests including tampering, no-op, false GPU claims, provenance spoofing, missing evidence and a 3,000-node DAG test |
| `experiments/ablation.py` | 42 controlled mutated examples and a transparent outcome-only reference baseline |
| `docs/` | Research methods, trust boundaries, PALE integration plan, 2026–2028 falsifiable research roadmap |

### The main interface

```python
from capegraph.fixtures import policy, cases
from capegraph.scoring import Outcome, grade

trusted_records, committed_effects = cases()["release"]
engine = policy()
audit = engine.evaluate(trusted_records, committed_effects)
assert audit.verdict == "PASS"
assert len(audit.certificates) == 1
```

### Core semantics

`PASS`: every *supplied* committed effect satisfies the declared action policy; evidence is current, independently sourced and authority-valid. `FAIL`: an explicit policy/provenance violation was observed. `UNVERIFIED`: there is not enough trusted proof for a conclusion (including conflicting contemporaneous authority facts). A `PASS` with zero effects **does not mean the task was completed**: the separate `grade` function gives it zero points.

A certificate includes IDs of the supporting records and SHA-256 fingerprints of canonical data. **It is not a digital signature or a standalone proof of log completeness.** Completeness and authenticity come from an operator-controlled, isolated service data plane. If that assumption fails or unobserved effects exist, CAPE cannot certify them. For long-term research, see `docs/RESEARCH_METHOD.md`.

### Reproducible existing PALE research work

This package's three task *domain fixtures* are new and smaller than the previously completed task-specific pilots. Their exact full pilots remain separately available in the private repository branches:

- `research/pale109-run-evidence-redteam-20261123`: 23/23 CPU provenance checks.
- `research/pale110-event-completeness-20261123`: 33/33 accessibility and consent checks.
- `research/pale119-integrated-redteam-20261123`: 41/41 release and contributor credit checks.

The existing 97-test archive is supplied alongside this repository prototype in the downloadable handoff bundle; do **not** add 97 and 59 to produce official PALE validation counts. Both are local unit-test results, not designated GPT, Claude, or Gemini fresh-state evaluations.

### Official status

PALE upstream PRs [#109](https://github.com/MatrAIx-ai/Personal-Agents-Last-Exam/pull/109), [#110](https://github.com/MatrAIx-ai/Personal-Agents-Last-Exam/pull/110), [#119](https://github.com/MatrAIx-ai/Personal-Agents-Last-Exam/pull/119) are currently design-stage, unapproved and unmerged. The public runtime's Infra/Messaging event controls are useful integration targets, but the official Task implementation interface and designated model roster must be frozen with the maintainers before actual implementation and agent trials.

### Prior work (not originality claims)

- Gaia2 (2026): dynamic and asynchronous agent environments, write-action verification, [arXiv:2602.11964](https://arxiv.org/abs/2602.11964).
- Chuang et al. (ACL 2026): proxy state-based verifiable rewards for multiturn agents, [ACL Anthology](https://aclanthology.org/2026.acl-industry.87/).
- *Do Agent Benchmarks Do What They Say?* (2026): executable-contract audit of tool environments, [arXiv:2609.37315](https://arxiv.org/abs/2609.37315).
- *Agentic Execution Assurance* (2026): observation-bounded three-valued assurance and trust/evidence semantics, [public paper](https://saridakisstamatischristos.github.io/publications/agentic-execution-assurance/agentic-execution-assurance.pdf).

**Research hypothesis, not yet a verified novelty claim:** combining current-event evidence, history-scoped authorization, complete effect enumeration, explicit positive scoring and counterfactual interventions may reduce oracle false-acceptance while retaining valid alternative workflows. Deterministic synthetic controls establish implementation correctness, not external novelty or transfer.


## CAPE-Robust v0.4 — prior-shift-aware verification (2026-11-24)

`capegraph/robust.py` adds **globally coupled finite-prior max-min planning** of read-only proof queries. It never uses the latent world label during execution and never switches the adversarial prior independently after each observation. The solver is exact for **deterministic policies** in a bounded finite model, using componentwise Pareto pruning of world-by-world reward/cost vectors. Mixed strategies and large-state robust POMDPs are not solved.

```bash
python -m unittest discover -s tests -v
python experiments/robust_benchmark.py
python run_all.py
```

New verified output: **96/96** framework tests (previous 81 plus 15 robust regression cases), prior separate **97/97**, 42 earlier falsification mutants, 363 static query cases, 243 finite-belief cases and **184/184** globally coupled prior cases compared against an independent decision-tree enumerator (180 frozen seeds + 4 deliberately designed). A strong shifted-prior counterexample gives robust worst-case expected proof reward **6** versus the nominal prior policy's **1**. The four-world coupled counterexample gives robust adaptive **4.5** versus globally robust fixed-plan **0.5**. On random seeds robust outperforms nominal in just **1/180** and equals it otherwise under the defined ambiguity set; on an additional out-of-set prior probe it can also lose. These synthetic outcomes do not establish generalized safety, an empirical SOTA advantage, or eligibility for authorship.

For the objective, exactness theorem, realistic threat model, independent oracle and full raw results see [`docs/CAPE_ROBUST_METHOD.md`](docs/CAPE_ROBUST_METHOD.md) and [`experiments/robust_results.json`](experiments/robust_results.json).


## v0.7 — CAPE-Certified (2026-11-24)

New shared observation-DAG exact pricing, anytime multi-prior strategy generation, sparse realization-flow LP and exact rational certificate verification, with observation-only execution. See [method and proof](docs/CAPE_CERTIFIED_METHOD.md). The 120 small synthetic cases and six scaling cases all have zero certified optimality gap. 24-world constructed stress: 149 nodes, 271 LP variables; robust reward 5 vs fixed-mixture 1.25. Seven repeated solves give 42.7x median flow/column runtime improvement on that specific case, not on general tasks. 134 framework + 97 separate prior tests pass locally. Run `python -m pip install -r requirements-v07.txt`, `python -m unittest discover -v -s tests` and `python experiments/certified_benchmark.py`. No external validation or official authorship claim.
