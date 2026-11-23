# CAPE-Contract v0.6: Counterexample-guided minimal evidence contracts

**Execution date 2026-11-24. Research prototype, not an official PALE verifier, submitted paper, or proof of external generalization.**

## Problem

Given a **task-owner-declared finite candidate vocabulary** of typed evidence obligations, independently labeled service trajectories, and a requirement that every known positive remain valid, synthesize a low-cost conjunction that accepts all development positives and **does not affirm** any development negative. Missing evidence is `UNVERIFIED`, never automatically `FAIL`. The synthesized conjunction is a *positive-outcome gate* and is always composed with the separate CAPE-Graph effect and authority verifier; it cannot replace full action-log verification.

A candidate obligation a = (token, expected value, allowed issuers, [not_before, not_after], cost) is evaluated using the latest allowed issuer/time-valid record, with same-time conflicts resulting in non-acceptance. Each candidate is derived from a fixed, reviewable task/schema specification **before** labels are inspected; no arbitrary marker or hidden oracle state may be inserted to separate examples. Source authentication is enforced by an independent trusted service adapter; the `issuer` string inside a hand-written `Witness` is not cryptographic authentication.

## Reduction and exact objective

Let P be the finite development valid set, N the finite development invalid set, and A the candidate atoms. First retain only P-compatible candidates:

A_P = {a in A : for every p in P, satisfies(a,p)}.

For each n in N define the witness set W(n) = {a in A_P : not satisfies(a,n)}. A conjunction C is development-separating iff every negative n has at least one selected failed atom: C ∩ W(n) ≠ ∅. Among separating C, minimize **sum of positive atom costs**, then the number of selected atoms, then the tuple of atom names lexicographically. This is a weighted hitting-set problem, **not a novel computational complexity result**. Selecting only P-compatible atoms gives perfect positive acceptance *on the development positives*, and selecting one atom from every negative's failed set gives abstention on every development negative.

**Theorem 1 (finite-pool separability and exactness).** Under a fixed finite candidate vocabulary and deterministic observation semantics, a contract of this conjunction form separates the developer-labeled finite pool if and only if each development negative has at least one failed P-compatible atom. If it exists, the branch-and-bound solver returns a minimum-weight separating contract with the specified secondary tie-break.

**Proof.** If a negative satisfies all P-compatible atoms, every positive-preserving conjunction accepts it, so separation is impossible. Otherwise choose one failed atom for each negative; the union is a separating contract. Every admissible separating conjunction intersects each nonempty W(n). Branching on an uncovered negative and enumerating its remaining failed atoms explores every such hitting set; a branch with current cost already equal to the best fully covering cost cannot improve it because all costs are strictly positive. Complete leaves are scored using the declared lexicographic objective. The best leaf is therefore optimal. □

**Theorem 2 (CEGIS certificate).** When the loop terminates with a separating contract, it is optimal for the *entire developer negative pool*, even if most negatives were added as counterexamples only after the initial solution.

**Proof.** The final candidate is optimal for its accumulated subset of negative constraints and is feasible for every negative in the full finite pool. Any lower-cost full-pool solution would also satisfy the accumulated subset and contradict the solver's optimality there. □

These are exact **finite-pool** statements; they do not certify unknown trajectories, mislabeled trusted records, omitted effects, or future tool versions. There is no universal false-acceptance guarantee under arbitrary unseen changes.

## Decisive evidence boundary

The returned contract is a *necessary positive-evidence check*. A trust-boundary-independent global effect verifier must still process the complete committed-effect log:

```
CAPE-Contract PASS + CAPE effect audit PASS   -> candidate PASS
CAPE-Contract UNVERIFIED + effect audit PASS -> UNVERIFIED
CAPE-Contract PASS + effect audit FAIL       -> FAIL
CAPE-Contract PASS + effect audit UNVERIFIED -> UNVERIFIED
```

An empty contract is never counted as PASS. If the same authenticated observation vector is assigned both positive and negative labels, the system returns `UNIDENTIFIABLE` rather than fabricating a separating rule. Hashes provide reproducibility, **not** signed source authentication or completeness guarantees.

## Tests and independent baseline

- `tests/test_contracts.py`: 12 tests including **210 fixed-seed random independent exhaustive-oracle comparisons**, exact cost/tie behavior, contradictory newest facts, source/time checks, non-identifiability, positive preservation and side-effect audit dominance.
- `experiments/contract_benchmark.py`: 3 independent fictional domains (release, lab protocol, delivery). Each has 6 development valid traces, 20 development invalid traces and 6 owner-declared candidate atoms. CEGIS adds only the counterexamples it sees. A second combinatorial enumerator independently confirms the result, and a cost-based greedy set-cover baseline is recorded.
- Frozen split: **405 valid and 450 invalid** traces across the 3 domains, independently seeded and not supplied to the CEGIS loop. Of the valid traces, **45 have an explicitly changed legitimate source channel** and are correctly *withheld* by the fixed source schema rather than silently accepted. Of the invalid traces, **90 have completely valid-looking witness vectors but unrelated unauthorized committed effects**; a witness-only contract falsely accepts 90, while the independent CAPE full-effect guard catches all 90 in these controlled synthetic records. This is a *negative result that motivates full-effect auditing*, not a claim of 100% real-world safety.
- Engineered weighted hitting-set case: the exact synthesizer uses 2 atoms versus a local greedy set-cover baseline's 3, with the same positive/negative rules. This is a known set-cover trap, not evidence of beating the strongest published synthesis method.

No hidden benchmark solution is used for contract training. Test examples are synthetic and structured by the same task author as the development examples. Even with disjoint random seeds, this is **not an independent distribution shift** or actual held-out agent rollouts. The source-migration scenario shows a meaningful schema drift but is also author-constructed.

## Relationship to current research (2026)

- **VerifierBench (Oct 2026)** benchmarks generated executable task verifiers against ordinary errors, alternative valid solutions and attacks; a controlled mapping to its public task schemas is the next externally grounded comparison. 222 source tasks and 4,993 hidden tests are not available to or used in this experiment. https://arxiv.org/abs/2610.28679
- **Do Agent Benchmarks Do What They Say? (Sep 2026)** shows that response text can masquerade as committed service state; this supports keeping the independent effect verifier in the evaluation pipeline. https://arxiv.org/abs/2609.37315
- **ContractBench (NeurIPS 2026)** covers tool-observation contract validity/integrity; CAPE does not replace such byte-/clock-aware checks. https://github.com/SecurityLab-UCD/ContractBench
- **AutoSpec / ICE / CEGIS** investigate counterexample-driven program and safety-specification synthesis. Learning constraints from positive/negative examples, optimal set cover and CEGIS themselves are prior art and **are not claimed as unique inventions**.

## Priority extensions, ordered for 2027/2028 competitiveness

1. **Real service-owned logs and external verifiers:** freeze a public tool-task subset, run actual environment commits and model rollouts with complete effect capture. Evaluate per-task false acceptance, valid alternative solution acceptance, abstention coverage, runtime and operator review time.
2. **Contract language expressivity:** extend a pure conjunction into guards, disjunctions, temporal obligations, scoped grants and revocations. Mine realistic action schemas *without allowing a task to invent trusted issuers*. Test exactness separately, as branch-and-bound no longer covers the richer logic automatically.
3. **Risk-aware active counterexample selection:** choose verifier queries to maximally reduce uncertainty about candidate contract equivalence under explicit query budgets, using CAPE-Adapt/Mix and independently scored unseen source drift.
4. **Formal counterexample completeness:** assume full effect-log enumeration or return `UNVERIFIED` if the data plane cannot certify closure. Preserve indistinguishability certificates when two different committed worlds look identical to the available observer.
5. **Robustness:** freeze candidate vocabularies before evaluation; measure holdout performance under source migrations and posterior misspecification instead of reporting training-set separation as generalization.

The v0.6 artifact is an executable small-model scientific baseline and a falsifiable design for the next experiment—not a claim of 2027/2028 top-conference acceptance.
