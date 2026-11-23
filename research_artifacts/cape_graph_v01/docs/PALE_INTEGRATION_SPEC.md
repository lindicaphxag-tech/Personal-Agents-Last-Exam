# PALE integration boundary — design compatibility, not a deployed adapter

Verified PALE public `runtime/README.md` as of 2026-11-24 states that Infra supports `env.load_seed`, `env.apply_event`, `env.reset`, `env.snapshot`, `env.event_status`, `env.validate_bundle` and `env.advance_time`. It also describes a separate Agent/Infra tool plane and Messaging receipts. `main` currently does not expose an officially accepted Task implementation directory for these three proposals.

## Integration sketch

1. A **trusted harness**, never the evaluated agent, opens the permitted Infra connection and snapshots the deployed Apps after each user-message-opened session.
2. A Task-specific adapter maps **only actual service-issued events** and exact permission/identity records into the CAPE trusted fact/grant/revoke channel, with authenticated source identities. The agent's own messages cannot be added to this channel merely by containing an issuer name.
3. A second operator-controlled ledger maps **every committed side-effect** (outgoing Messages/CMS posts, scheduler jobs, item transfers/receipts) into CAPE effects. It must enumerate *all* side effects, including unplanned ones; a curated list of expected actions is insufficient.
4. The completed application state and timeline are graded with CAPE policy clauses, then the reviewer-approved Task rubric performs *separate* expected-outcome scoring. Safe alternative sequences, semantic paraphrases, existing authorization and current user instructions must remain valid.
5. Protected snapshots and grader secrets are never shared with the candidate. Only permitted user history and App responses are visible to the agent.

## Task mappings to validate **after** reviewer approval

| Task | Protected evidence producers | Representative output predicates | Protected side effects |
| --- | --- | --- | --- |
| #119 Release attribution | version registry, tag/signature verifier, accepted contributor ledger, user approval | published release, asset signature valid, software credit accepted | CMS publish/draft/hold, private/public notices, idempotency |
| #109 CPU research | signed protocol/holdout, quota service, actual trusted scheduler | exact frozen IDs, training-only fit, CPU job success, GPU unexecuted | job execution receipts, artifact writes, delivered report |
| #110 Step-free delivery | facilities route closure, volunteer consent backend, item custody/dispatch receipt issuer | reachable step-free route, item-specific consent, actual delivery | transfer, dispatch and notification, preserved original receipt |

### Hard constraints

- No official Task run is simulated from `env.snapshot` alone; verifying *external* execution requires service-issued receipts.
- No model performance or acceptance can be inferred from 59 new unit tests, 42 synthetic mutations or prior 97 tests.
- The provided `ingest_service_streams` is a **mockable interface contract**. The concrete PALE serializer and protected event fields are **not** assumed; adapter validation must be done against the maintainer-approved runtime/version.
- Revisions to approved rubric/Task design go back to design review; unapproved upstream PR files are not modified by this research branch.
