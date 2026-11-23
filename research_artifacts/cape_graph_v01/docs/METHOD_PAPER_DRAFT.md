# CAPE-Graph: Counterexample-Guided Evidence Contracts and Retractable Proof-Carrying Rewards for Stateful Agents

**Version 0.2 — exploratory research manuscript, 24 November 2026**

**Author:** Zhibo Zhang, Hangzhou Dianzi University.  
**Repository:** `lindicaphxag-tech/Personal-Agents-Last-Exam`, branch `research/cape-graph-v02-20261124` (independent author-side research branch).  
**Scientific status:** Research prototype and reproducible synthetic experiments. Not an accepted venue paper, an official PALE task, or a claim of PALE manuscript co-authorship.

## Abstract

An autonomous agent may satisfy the visible fields of a benchmark rubric while relying on fabricated evidence, unauthorized actions, duplicated side effects, or facts from unrelated executions. We study the distinction between a locally valid witness and an independently grounded outcome in three synthetic stateful personal-agent tasks: experimental protocol integrity, volunteer delivery with item-specific consent, and software release communication with prior-history-dependent permissions. We introduce **CAPE-Graph**, a typed provenance and authority verifier with three-valued results and positive-outcome scoring, and extend it with **CECS**, a cost-aware finite-grammar counterexample-guided screening learner, and **PCR**, a replay-verified reward with revocable provisional credit. A new relational proof condition enforces that individually genuine evidence records belong to the *same declared execution dependency chain*. The current implementation passes **100 framework unit tests** and **97 independent domain-pilot tests**. Across 42 programmer-authored mutations, a weak expected-value-only baseline falsely accepts 36, whereas the full verifier accepts none. On a previously omitted causal-disconnection family, an initial screen defers three cases; one counterexample then induces a relational check which flags all three. Sixty semantically equivalent identity-renamed references remain valid. Finally, in a deliberately reward-hackable **one-step synthetic contextual bandit**, 30/30 learned policies using certificate reward select the legitimate action, compared with 0/30 using naive apparent-success reward. These results establish functional, reproducible proof-of-concept behavior, **not** generalization or statistical superiority over published agent benchmarks.

## 1. Problem and scope

We separate four objects that an agent benchmark often conflates: (i) the model's own report, (ii) a log of committed tool side effects, (iii) issuer-controlled evidence records, and (iv) the complete observable task outcome. A model's plausible wording can coexist with an invalid service state. Likewise, a SHA256 hash of an agent-authored event list establishes only byte consistency, not that an independent service executed the action.

Let $T$ be a sequence of authenticated service-controlled records, $E$ a complete committed action-effect stream, $\pi$ a versioned policy and $G$ a positive-outcome rubric. We seek a function $V_\pi(T,E)\in\{\mathrm{PASS},\mathrm{FAIL},\mathrm{UNVERIFIED}\}$ with explicit witness provenance and an independent score $S_G(T,E)$. The guarantee is **conditional** on a trusted and complete observation plane. If an external side effect is not logged, no log-based verifier can infer it in general.

### Prior-art boundary

Counterexample-guided synthesis is an established program-synthesis paradigm, and work published in 2026 examines benchmark reward hacking, formal instrumentation, process-verifiable rewards and auditor-trace completeness. Relevant comparators include *BenchShield* (arXiv:2609.11028), *Do Agent Benchmarks Measure Capability?* (arXiv:2607.22368), *Optimistic Verifiers Get Hacked* (arXiv:2611.21538), *Process Reward Agents* (ICML 2026) and *Verifiable Process Rewards for Agentic Reasoning* (AAMAS 2026). Our contribution at this stage is an **executable combination and falsification study**, not a priority claim over these publications. Strong empirical novelty requires external datasets, model-agent experiments and genuinely comparative implementations.

## 2. Framework

### 2.1 Evidence and authority representation

Each trusted record has an independently assigned issuer channel and an event time. Records are typed as facts, scoped grants or grant revocations. Each committed side effect has a principal, action, scope, event time, typed claims, issuer witness IDs and an idempotency key. The agent's self-report cannot populate the trusted channel. A strict adapter binds issuer identity from the authenticated ingestion channel, not from any agent-supplied `issuer` field.

An individual effect is valid only if (i) its action contract and schema are known, (ii) an effective and unrevoked permission covers actor, action, scope and time, (iii) each required outcome is grounded in issuer-authoritative evidence, (iv) any source facts are current and nonconflicting, (v) all causal parent records exist and predate their dependents, and (vi) no duplicate or unregistered irreversible side effects are committed. Missing proof leads to `UNVERIFIED` unless another independently observed violation requires `FAIL`. An empty effect stream can pass a *safety audit*, but **earns zero positive task score**.

### 2.2 New: relational proof binding

A set of separately authentic facts does **not** necessarily prove one coherent workflow. For required predicate pairs $(p_c,p_a)$, the contract now specifies a directed path from the child-predicate witness to the ancestor-predicate witness in the trusted provenance DAG:

$$\operatorname{bound}(p_c,p_a) = \mathbb{1}[w(p_a)\in\operatorname{Ancestors}(w(p_c))].$$

The current three task contracts require: signed release asset evidence to descend from the published release record; a successful CPU job receipt to descend from the approved frozen protocol; and a completed delivery receipt to descend from both specific volunteer consent and the valid route state. This is **operational dependency provenance**, not identification of causal treatment effects in the statistical sense. A counterexample can preserve each record's legitimate issuer and value but remove a causal parent edge, exposing previously missing checks.

### 2.3 CECS: finite-grammar counterexample-guided screening

Define a finite library of candidate checks $H=\{h_1,\dots,h_K\}$ for schemas, declared actions, required outcomes, permission scope/time, witness matching, fact freshness, uniqueness, ancestry, timestamps and relational dependency. Each guard has an explicit integer cost proxy $c_i$ and returns a Boolean *risk flag* on a complete synthetic trace.

Given oracle-confirmed positives $P$ and oracle-disallowed negatives $N$, reject any guard that flags a positive, then greedily add the guard maximizing

$$\frac{|\{x\in N_{\mathrm{uncovered}}:h_i(x)=1\}|}{c_i}.$$

Repeat until every available negative is covered or no guard improves coverage. The learned policy returns only `REJECT` (flagged for review) or `DEFER` (no inexpensive evidence of a defect); **neither is a success certificate**. Complete CAPE evaluation remains necessary before issuing PASS or positive task reward. The algorithm's finite-example coverage and cost proxies are not proofs of globally minimal policy, asymptotic acceleration or zero false rejections on unseen valid data.

A novel negative family was excluded from the initial 14-type mutation grammar: detach the otherwise authentic issuance record's causal parent links. Initially CECS deferred all three examples to the full verifier. Revealing *one* detached CPU-receipt counterexample and re-running selection caused CECS to include the relational guard and flag the corresponding release and delivery examples. Those are two in-suite cross-domain transfers, not independently collected external cases.

### 2.4 PCR: retractable proof-carrying reward

For each prefix $E_{\le t}$, evaluate the **full** verifier and scored outcome. Let

$$q_t=\begin{cases}S_G(T,E_{\le t})/S_{\max}, & V_\pi(T,E_{\le t})=\mathrm{PASS},\\0, & \text{otherwise.}\end{cases}$$

Define the incremental reward $r_t=q_t-q_{t-1}$ with $q_{-1}=0$. Therefore the *telescoping identity* $\sum_{t=0}^T r_t=q_T$ holds exactly up to floating-point rounding. This removes duplicate provisional pay for a completed goal and permits **negative clawback** when a later illegal event invalidates the complete run. No positive reward is provided for an unresolved or failed prefix.

Each reward record contains the current verdict, outcome points, referenced service effect IDs, the policy version fingerprint, full evidence-stream fingerprint and a separate digest of the underlying verifier proof. A purported reward certificate is **never trusted as an input**: `verify_reward_trace` replays the original service records under the pinned policy and checks the recomputed reward and proof metadata for equality. SHA256 is a replay fingerprint, not a digital signature or proof that the issuer was authentic. This design is an interface for future RL research; the current learning demonstration is a tabular synthetic contextual bandit rather than a deployed RL agent.

### 2.5 Threat model and guarantees

An agent may emit untrue claims or unauthorized actions but cannot alter the trusted service ingestion channels or read protected signing keys. The *test author* can mutate and re-sign synthetic records for falsification. This is not an agent key compromise. The framework guarantees that no positive PCR reward is emitted without the full verifier returning PASS **under the supplied trusted records**. It cannot prove the completeness of a compromised external service stream, automatically infer hidden unlogged events, or certify free-form language semantics without a separately evaluated claim-extraction layer.

## 3. Controlled experiments

All test cases are fully synthetic and programmatically authored. The 2026-11-24 version is reproducible under Python 3.11–3.13 without paid model APIs.

| Experiment | Sample size / setup | Result |
| --- | --- | --- |
| Full regression | 100 new CAPE tests + 97 independent PALE domain-pilot tests | **197/197 passed locally** |
| Original invalid mutations | 3 domains × 14 predeclared attack modes | Expected-value-only baseline accepted **36/42**; full CAPE accepted **0/42** |
| Initially held-out causal-connection family | Remove one critical dependency from an otherwise genuine proof | Initial CECS deferred **3/3**; complete verifier failed **3/3** |
| One-counterexample refinement | Expose detached CPU receipt to CECS | Relational guard added; flags **3/3** including 2 other domains |
| Metamorphic positive tests | 3 cases × 20 deterministic identity remappings and event shuffles | **60/60 PASS**, **0 fast-screen false flags** |
| PCR reference and retraction | 3 reference tasks plus appended unauthorized effect | Positive references **3/3** receive 1.0; late infringement causes **3/3** clawbacks to 0 |
| Synthetic tabular contextual bandit | 3 domains × 10 seeds × 350 episodes / reward type | Naive reward: **0/30** learned valid actions; PCR: **30/30** |

#### Important control in the toy learning experiment

The environment intentionally makes an unverified fabricated receipt **cost-free** and a legitimate authorized action cost 0.10 reward units. The naive reward is *explicitly programmed* to reward the presence of correct-looking output fields while ignoring authorization and issuance; this construct causes agents to learn the shortcut. The certificate reward is programmed to require the full verifier to pass; this makes the legitimate action optimal. These two settings are constructed to contrast training signals, not to estimate improvement over advanced real-world reinforcement-learning methods. The learning method is a simple epsilon-greedy single-state value learner, not PPO, GRPO, VLA or LLM reinforcement learning.

## 4. Controls, audit, and limitations

A scientifically complete comparison still requires independently collected tasks with unknown service state, real model-agent trajectories, robust human-annotated free-text parsing, formal external channel authentication, comparison against existing benchmark verifiers and reward methods, and estimates of false acceptance, false rejection and abstention under distribution shift. No benchmark-specific official GPT/Claude/Gemini trials were performed. Permission-aware checks must reflect approved platform boundaries and must not silently introduce a new requirement to the three existing upstream PALE task proposals.

The 197 unit tests measure implementation behavior of known checks; they are not 197 independent benchmark trajectories or evidence of SOTA accuracy. The 60 metamorphic tests alter syntactic identities while preserving the same three underlying task structures. The 42 attack modes and the detached family were author-designed. The simulator does not recreate the full PALE agent platform, and no review has certified the new framework as an approved PALE contribution.

## 5. Concrete forward work and publication gate

1. **First official Task acceptance:** obtain maintainer `/approve-plan` for existing PALE #119, #109, #110 separately; implement each approved runtime task under `tasks/` in the same PR and supply proof-backed outcomes, reset, reproduction and official designated GPT/Claude/Gemini rollouts. Do not treat a research fork branch as a merge.
2. **Independent validity study:** recruit a distinct task author/evaluator, freeze the blind test set, compare to actual external baselines, measure uncertainty/calibration, and preregister false-accept and false-reject criteria.
3. **Formal CECS upgrade:** synthesise contracts from a constrained grammar with SMT/temporal logic; use true equivalence classes and an independent counterexample oracle instead of only the greedy nine-guard library.
4. **Real PCR training:** evaluate task completion and reward hacking in a larger multi-step, tool-using policy-learning environment under strict service/agent isolation, using matched compute and seed budgets. Log actual reward costs and prove that certificate replay is mandatory.
5. **Manuscript authorship:** the above experimental work and this draft are concrete independent research contributions. Authorship in the PALE team's paper is a separate maintainer decision requiring three accepted tasks (or three accepted environments) and substantial paper participation.

## References (verification background)

- *BenchShield: Formal Model-Backed Instrumentation for Reward Integrity in LLM-Agent Evaluation Infrastructure*. arXiv:2609.11028 (2026). https://arxiv.org/abs/2609.11028
- *Do Agent Benchmarks Measure Capability? Protocol Validity in the Age of Agentic AI*. arXiv:2607.22368 (2026). https://arxiv.org/abs/2607.22368
- *Optimistic Verifiers Get Hacked: Reward Hacking Under an Exact Process Oracle*. arXiv:2611.21538 (2026). https://arxiv.org/abs/2611.21538
- Sohn et al., *Process Reward Agents for Steering Knowledge-Intensive Reasoning*. Proceedings of ICML 2026. https://proceedings.mlr.press/v306/sohn26a.html
- *Verifiable Process Rewards for Agentic Reasoning*. AAMAS 2026; arXiv:2605.10325. https://arxiv.org/abs/2605.10325
- *Counterexample Guided Learning in the Large using Reasoning Agents*. arXiv:2606.11521 (2026). https://arxiv.org/abs/2606.11521
