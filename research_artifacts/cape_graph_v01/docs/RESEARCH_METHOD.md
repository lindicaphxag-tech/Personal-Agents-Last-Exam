# Research methods and falsifiability — CAPE-Graph

**Version 0.1 / 2026-11-24.** These are executable design hypotheses, not accepted paper claims.

## Research question

How can a tool-using personal-agent evaluator distinguish task success from unsupported claims, authentic but irrelevant records, stale facts, and unauthorized side effects across heterogeneous Apps, while permitting alternative valid strategies?

## Typed state model

A *trusted record* is either `fact`, `grant` or `revoke`; an independent *committed effect* contains an action, actor, scope, time, positive structured claims, issuer witness IDs and an idempotency key. Only records from verifier-controlled and authenticated service streams may enter the trusted channel; the external service log must also include **all** committed effects. The candidate agent's free-form self-report is neither trusted evidence nor a committed effect.

A fact `f` may depend on earlier facts in a directed acyclic evidence graph. Each claimed outcome has a required service-issuer domain and is checked at the actual effect time, using the latest non-conflicting trusted state. Grant/revoke records form a time-indexed authority graph. The action policy specifies the required observable outcome predicates, the expected values, allowed claims and the subset bound to the action target.

The prototype computes for each effect:

```
authorized_actor_at_time
∧ all_declared_claims_source_attested
∧ all_required_outcomes_present_and_correct
∧ causal_ancestors_valid
∧ no_conflicting_or_superseding_trusted_fact
∧ no_unknown_or_duplicate_irreversible_effects
```

A global `PASS` requires every supplied effect to meet its contract; observed violations yield `FAIL`; insufficient or contradictory evidence with no definite violation yields `UNVERIFIED`. **Positive task attainment is evaluated separately**: absence of wrongdoing is not success. A validated output receives a reproducible *proof witness list* and canonical SHA-256 fingerprints, which are useful for audit diffing but are not cryptographic proof of independent issuance.

The graph is *causal provenance* (explicit event dependencies), **not** identification of causal treatment effects in the statistical sense. The algorithm runs iterative DAG validation, time-indexed fact checks, and evidence-closure extraction. For bounded clauses and witnesses, the index-based core has approximately `O((V+E) + F log F + C log F)` policy-check work, ignoring output serialization and repeated certificate closure; `V+E` includes trusted graph vertices/edges, `F` fact records, `C` individual action claims. A large number of effects with large overlapping witness closures can create additional work; benchmarks must measure this.

## Counterexample-guided audit

Each synthetic domain starts with one independently known valid reference. We introduce 14 predeclared mutations per domain, separately changing authorization, fact issuer, evidence pointer, factual currency, side-effect completeness, required outcome status and causal timing. This produces **42 known-invalid examples** without agent behavior sampling. A deliberately weak baseline only checks expected values in at least one effect and ignores all other state. Results from the exact pinned script:

| Metric | Weak outcome-only ablation | CAPE-Graph |
| --- | ---: | ---: |
| Known invalid examples | 42 | 42 |
| Incorrectly accepted invalid | 36 | 0 |
| Explicitly rejected | 6 | 36 |
| Withheld pending trusted proof | 0 | 6 |
| Valid reference scenarios | 3 | 3 |

The 42 variants are programmatically authored and are **not random samples**. There is no statistical inference about real-world false-positive rates or reference-model difficulty. Unlike a benchmark training/test split, these scenarios were used during development and are *not held-out*.

## Identifiability and evidence limitations

Two different worlds can produce the same visible logs while differing in a hidden side effect. No log-only checker can generally decide which world occurred. Thus a CAPE `PASS` is **conditional on completeness/authenticity of the operator-controlled observed data** and an exhaustive policy for declared effects. CAPE cannot infer events the source never records, nor verify human intent from an ungrounded natural-language paraphrase. Three-valued output prevents one common false-certificate pattern, but unknowns can still be misclassified if the underlying service falsely asserts a fact.

The current prototype is deliberately strict about typed claims. In a real PALE implementation, a semantic normalization adapter must map equivalent natural-language statements to **evidence-backed typed claims**, accept safe paraphrases, and assess its own extraction errors on held-out human annotations. The agent may never see hidden grader prompts, issuer secrets or protected canonical truth labels.

## Experimental roadmap necessary for a serious publication

1. **Independent validation sets**: create new tasks, services, temporal histories and adverse cases by independent collaborators, not reuse the construction examples; preregister bug categories and expected outcomes.
2. **Comparative baselines**: state-only verifier; pure transcript judge; state plus auth; state plus provenance; CAPE full; compare on the *same* operationally verified live traces.
3. **Validity metrics**: false acceptance and false rejection (with confidence intervals), unknown/coverage trade-off, source attribution accuracy, consistency with human review, minimal counterexample quality and end-to-end runtime.
4. **Ablation study**: disable issuer binding, temporal supersession, full effect enumeration, past authorization or positive-outcome checks individually; quantify contribution without cherry-picking.
5. **Model-agent trials**: after official PALE plan approval, use dated, versioned GPT/Claude/Gemini models, frozen scenario and grader settings, independent fresh resets, unhinted and hinted conditions, and all complete trajectories (no successful/failing subset selection).
6. **Protected implementation**: issuer references must be generated from authenticated Infra/Messaging/dispatch/scheduler events; prohibit evaluator test keys inside the candidate process, require append-only stream checks, and make log omission auditable.

## Known limitations today

This is an exploratory, deterministic local simulator. It does not yet execute against the PALE official Task runner, verify real network delivery, judge free-form claims, reproduce other public benchmarks, produce held-out multi-model scores, nor show publication-level novelty or SOTA improvement. The model roster, interfaces, maintainer approval and co-authorship decision are independent gates.
