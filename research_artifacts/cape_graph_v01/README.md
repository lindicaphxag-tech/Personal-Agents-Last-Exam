# CAPE-Graph v0.1 — Causal, Authority-aware, Provenance-grounded Evidence Graph

**Research prototype, dated 2026-11-24** · Python 3.11+ standard library · CPU · zero paid APIs · author-side evidence for three unapproved PALE Task proposals.

**Goal:** Assess *all consequential committed actions* using time-indexed, issuer-bound evidence, scoped permissions and a separate positive-outcome rubric. A correct answer string or a signed agent-written trace is not evidence of a real service-side action.

### Quick start

```bash
python -m unittest discover -v -s tests
python experiments/ablation.py
python -m capegraph --case release --json
python -m capegraph --case notice_restrictive
python -m capegraph --case notice_permissive
```

**Current local result:** 59/59 framework unit tests. Three synthetic positive references PASS; 42 deliberately invalid cases are not accepted (36 `FAIL`, 6 `UNVERIFIED`). A transparent weak *outcome-only* baseline accepts 36/42 invalid examples. The baseline is **our own toy ablation**, not another published system. The same world facts with only the earlier public-notice authorization changed flip `FAIL` -> `PASS`. These are author-side deterministic experiments—not model-agent rollouts, generalizable reliability estimates, PALE merge, or authorship confirmation.

### What's inside

| Module | Purpose |
| --- | --- |
| `capegraph/core.py` | DAG provenance, issuer whitelist, time-bound permissions, revocations, stale/contradictory facts, complete effect audits, three-valued verdicts and proof-linked fingerprints |
| `capegraph/ingest.py` | Accept only pre-authorized *verifier-controlled* service channels; issuer identity is assigned by the controlled channel, not copied from an agent's JSON |
| `capegraph/scoring.py` | Independent positive outcome evidence; no-op receives 0 points even when the safety audit finds no violation |
| `capegraph/fixtures.py` | Synthetic release/credit, scientific CPU protocol and step-free item dispatch; includes a prior-history authorization counterfactual |
| `tests/` | 59 deterministic CPU tests including tampering, no-op, false GPU claims, provenance spoofing, missing evidence and a 3,000-node DAG test |
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
