"""CAPE-Graph: causal and authority-aware verification of stateful agent effects.

The trusted evidence log MUST come from verifier/Infra-only storage. Never put
untrusted agent-authored JSON into the trusted_log argument. All hashing below
is only for reproducibility; hashes alone DO NOT authenticate an event issuer.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict, deque
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Iterable, Mapping


def canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf8")


def digest(obj: object) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


@dataclass(frozen=True)
class Rule:
    action: str
    required: tuple[tuple[str, object], ...]
    allowed: frozenset[str]
    unique: bool = True
    scope_bound: frozenset[str] = frozenset()
    required_ancestry: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Finding:
    code: str
    effect_id: str
    detail: str
    evidence: tuple[str, ...] = ()
    unknown: bool = False

    def to_json(self) -> dict:
        return {
            "code": self.code, "effect_id": self.effect_id,
            "detail": self.detail, "evidence": list(self.evidence),
            "unknown": self.unknown,
        }


@dataclass(frozen=True)
class Result:
    verdict: str
    findings: tuple[Finding, ...]
    certificates: tuple[dict, ...]
    events_checked: int

    def to_json(self) -> dict:
        return {"verdict": self.verdict, "events_checked": self.events_checked,
                "findings": [x.to_json() for x in self.findings],
                "certificates": list(self.certificates)}


def _exact(record: dict, keys: set[str], where: str) -> None:
    if not isinstance(record, dict) or set(record) != keys:
        raise ValueError(f"{where}: expected exact fields {sorted(keys)}")


def _ident(value: Any) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 160


def _timestamp(value: Any) -> bool:
    return type(value) is int and 0 <= value <= 2**63 - 1


def _same(a: Any, b: Any) -> bool:
    return canonical(a) == canonical(b)


def _unique_claims(claims: list[dict]) -> bool:
    keys = [c["predicate"] for c in claims]
    return len(keys) == len(set(keys))


TRUSTED_FIELDS = {
    "fact": {"id", "type", "at", "issuer", "subject", "predicate", "value", "parents"},
    "grant": {"id", "type", "at", "issuer", "principal", "action", "scope", "not_after"},
    "revoke": {"id", "type", "at", "issuer", "grant_id"},
}
EFFECT_FIELDS = {"id", "at", "principal", "action", "scope", "claims", "grant_id", "idempotency_key"}
CLAIM_FIELDS = {"predicate", "subject", "value", "witness"}


class Verifier:
    """Policy, provenance, causality, communication truth and positive evidence.

    Complexity: O((N + M) log N) for indexed fact lookup and grant candidates,
    plus O(total parent edges) for causal dependency checking and certificates.
    N = trusted records, M = claims/effects, ignoring JSON serialization cost.
    """

    def __init__(self, rules: Mapping[str, Rule], fact_issuers: Mapping[str, set[str]],
                 grant_issuers: set[str]):
        self.rules = dict(rules)
        self.fact_issuers = {k: frozenset(v) for k, v in fact_issuers.items()}
        self.grant_issuers = frozenset(grant_issuers)

    def evaluate(self, trusted_log: Iterable[dict], effect_log: Iterable[dict]) -> Result:
        """The two inputs are from DIFFERENT controlled service-side channels.

        When evidence is incomplete, return UNVERIFIED (three-valued semantics).
        Any demonstrated policy violation returns FAIL, even if others are unknown.
        """
        trusted, effects = list(trusted_log), list(effect_log)
        findings: list[Finding] = []
        certificates: list[dict] = []
        nodes: dict[str, dict] = {}
        facts: dict[tuple[str, str], list[dict]] = defaultdict(list)
        grants: dict[str, dict] = {}
        revocations: dict[str, list[dict]] = defaultdict(list)
        trusted_ids: set[str] = set()

        # Exact schemas are checked *before* reading any untrusted field.
        for i, e in enumerate(trusted):
            if not isinstance(e, dict) or e.get("type") not in TRUSTED_FIELDS:
                raise ValueError(f"trusted record {i}: unknown type")
            _exact(e, TRUSTED_FIELDS[e["type"]], f"trusted record {i}")
            if not _ident(e["id"]) or not _ident(e["issuer"]) or not _timestamp(e["at"]):
                raise ValueError(f"trusted record {i}: invalid id/issuer/time")
            if e["id"] in nodes:
                raise ValueError(f"duplicate trusted id: {e['id']}")
            if e["type"] == "fact":
                if not (_ident(e["subject"]) and _ident(e["predicate"]) and
                        isinstance(e["parents"], list) and all(_ident(x) for x in e["parents"])):
                    raise ValueError(f"invalid fact at {i}")
                if e["predicate"] not in self.fact_issuers:
                    raise ValueError(f"unknown fact predicate: {e['predicate']}")
            if e["type"] == "grant":
                if not all(_ident(e[k]) for k in ("principal", "action", "scope")):
                    raise ValueError("invalid grant")
                if not _timestamp(e["not_after"]) or e["not_after"] <= e["at"]:
                    raise ValueError("invalid grant interval")
            if e["type"] == "revoke" and not _ident(e["grant_id"]):
                raise ValueError("invalid revocation reference")
            nodes[e["id"]] = e
            trusted_ids.add(e["id"])

        # A causal parent must pre-exist its child in trusted event chronology.
        # For equal timestamps, only explicit parent IDs establish ordering.
        for e in trusted:
            if e["type"] == "fact":
                for parent in e["parents"]:
                    if parent not in nodes:
                        raise ValueError(f"missing causal ancestor {parent}")
                    if nodes[parent]["at"] > e["at"] or parent == e["id"]:
                        raise ValueError(f"causally impossible ancestor {parent}")
                facts[(e["subject"], e["predicate"])].append(e)
            elif e["type"] == "grant":
                grants[e["id"]] = e
            else:
                revocations[e["grant_id"]].append(e)

        # Iterative Kahn topological validation avoids recursion depth failures
        # on thousands of causal dependencies and remains O(V+E).
        degree = {k: 0 for k in nodes}
        successors: dict[str, list[str]] = defaultdict(list)
        for e in trusted:
            for parent in e.get('parents', []):
                degree[e['id']] += 1
                successors[parent].append(e['id'])
        pending = deque(k for k, d in degree.items() if d == 0)
        processed = 0
        while pending:
            k = pending.popleft()
            processed += 1
            for child in successors.get(k, ()):
                degree[child] -= 1
                if degree[child] == 0:
                    pending.append(child)
        if processed != len(nodes):
            raise ValueError('trusted evidence dependency cycle')
        for key in facts:
            facts[key] = sorted([f for f in facts[key] if f["issuer"] in self.fact_issuers.get(key[1], set())],
                                key=lambda x: (x["at"], x["id"]))
        fact_times = {key: [f["at"] for f in seq] for key, seq in facts.items()}
        # Conflicting issuer-authoritative observations with equal effective time
        # are not decided by arbitrary ID/ingestion order: mark indeterminate.
        conflicts: set[tuple[str, str, int]] = set()
        for (subject, predicate), history in facts.items():
            by_time: dict[int, bytes] = {}
            for item in history:
                fingerprint = canonical(item['value'])
                key = (subject, predicate, item['at'])
                if item['at'] in by_time and by_time[item['at']] != fingerprint:
                    conflicts.add(key)
                by_time.setdefault(item['at'], fingerprint)
        for key in revocations:
            revocations[key].sort(key=lambda x: (x["at"], x["id"]))

        seen_effects = set()
        used_scopes: dict[tuple[str, str], str] = {}
        used_idempotency: dict[tuple[str, str], str] = {}
        for i, event in enumerate(effects):
            _exact(event, EFFECT_FIELDS, f"effect {i}")
            if not all(_ident(event[k]) for k in ("id", "principal", "action", "scope")) or not _timestamp(event["at"]):
                raise ValueError(f"effect {i}: invalid identity/action/time")
            if event["id"] in seen_effects or event["id"] in trusted_ids:
                findings.append(Finding("duplicate_effect_id", event["id"], "duplicate event ID"))
            seen_effects.add(event["id"])
            current_errors: list[Finding] = []
            proof_ids: set[str] = set()

            def fault(code: str, detail: str, *, evidence: tuple[str, ...] = (), unknown: bool = False):
                finding = Finding(code, event["id"], detail, evidence, unknown)
                current_errors.append(finding)
                findings.append(finding)

            rule = self.rules.get(event["action"])
            if rule is None:
                fault("unknown_effect", f"undeclared consequential action {event['action']}")
            if not _ident(event["grant_id"]):
                fault("missing_grant", "no authority grant ID")
            elif event["grant_id"] not in grants:
                fault("missing_grant", "authority grant not independently recorded")
            else:
                grant = grants[event["grant_id"]]
                proof_ids.add(grant["id"])
                if grant["issuer"] not in self.grant_issuers:
                    fault("untrusted_grant", "grant issuer not in trusted authorization registry")
                if not (grant["principal"] == event["principal"] and
                        grant["action"] == event["action"] and grant["scope"] == event["scope"] and
                        grant["at"] <= event["at"] < grant["not_after"]):
                    fault("unauthorized_scope_time", "actor/action/scope/time outside grant")
                if any(r["at"] <= event["at"] and r["at"] >= grant["at"] and
                       r["issuer"] == grant["issuer"] for r in revocations[event["grant_id"]]):
                    fault("revoked_permission", "grant revoked before action")
                if any(r["at"] <= event["at"] and r["issuer"] != grant["issuer"]
                       for r in revocations[event["grant_id"]]):
                    fault("untrusted_revocation", "revocation issuer does not match grant issuer")
            if not isinstance(event["claims"], list):
                raise ValueError(f"effect {i}: claims not a list")
            for j, c in enumerate(event["claims"]):
                _exact(c, CLAIM_FIELDS, f"effect {i} claim {j}")
                if not (_ident(c["predicate"]) and _ident(c["subject"]) and _ident(c["witness"])):
                    raise ValueError(f"effect {i}: malformed claim")
            claims = event["claims"]
            if not _unique_claims(claims):
                fault("duplicate_claim", "repeated claim predicate in one effect")
            claim_map = {c["predicate"]: c for c in claims}
            if rule is not None:
                for pred, expected in rule.required:
                    if pred not in claim_map:
                        fault("missing_required_claim", f"required claim {pred} absent", unknown=True)
                    elif not _same(claim_map[pred]["value"], expected):
                        fault("incorrect_required_claim", f"required claim {pred} differs")
                for pred in claim_map:
                    if pred not in rule.allowed:
                        fault("extra_claim", f"unregistered effect claim {pred}")
                if rule.unique:
                    key = (event["action"], event["scope"])
                    if key in used_scopes:
                        fault("duplicate_irreversible_effect", f"prior effect {used_scopes[key]}")
                    else:
                        used_scopes[key] = event["id"]
            if not isinstance(event["idempotency_key"], str):
                raise ValueError("invalid idempotency key type")
            if event["idempotency_key"]:
                idem_key = (event["action"], event["idempotency_key"])
                if idem_key in used_idempotency and used_idempotency[idem_key] != event["id"]:
                    fault("duplicate_idempotency", "repeated committed side effect, not an idempotent read")
                else:
                    used_idempotency[idem_key] = event["id"]

            # Relational proof binding: two separately authentic facts do not
            # automatically belong to the same operation. Require declared
            # descendant -> ancestor links between outcome witnesses. These
            # are provenance dependencies, NOT statistical causation.
            if rule is not None:
                for child_pred, ancestor_pred in rule.required_ancestry:
                    child_claim = claim_map.get(child_pred)
                    ancestor_claim = claim_map.get(ancestor_pred)
                    if child_claim is None or ancestor_claim is None:
                        continue  # Missing required claims already get UNVERIFIED.
                    child_id, ancestor_id = child_claim["witness"], ancestor_claim["witness"]
                    if child_id not in nodes or ancestor_id not in nodes:
                        continue  # Missing witnesses already get UNVERIFIED.
                    reachable = set()
                    stack = list(nodes[child_id].get("parents", []))
                    while stack:
                        parent_id = stack.pop()
                        if parent_id in reachable:
                            continue
                        reachable.add(parent_id)
                        stack.extend(nodes[parent_id].get("parents", []))
                    if ancestor_id not in reachable:
                        fault("unbound_cross_service_proof",
                              f"{child_pred} witness not causally dependent on {ancestor_pred}",
                              evidence=(child_id, ancestor_id))

            for c in claims:
                if rule is not None and c["predicate"] in rule.scope_bound and c["subject"] != event["scope"]:
                    fault("wrong_subject_scope", f"{c['predicate']}: claim is not about action target")
                witness = nodes.get(c["witness"])
                if witness is None:
                    fault("missing_witness", f"no independently recorded proof for {c['predicate']}", unknown=True)
                    continue
                proof_ids.add(c["witness"])
                if witness["type"] != "fact":
                    fault("not_a_fact", f"witness for {c['predicate']} is not factual evidence")
                    continue
                if witness["issuer"] not in self.fact_issuers.get(c["predicate"], set()):
                    fault("untrusted_issuer", f"{c['predicate']}: wrong evidence issuer")
                if witness["at"] > event["at"]:
                    fault("future_evidence", f"{c['predicate']}: fact issued after effect")
                if not (witness["subject"] == c["subject"] and
                        witness["predicate"] == c["predicate"] and
                        _same(witness["value"], c["value"])):
                    fault("mismatched_witness", f"{c['predicate']}: witness does not match claim")
                # A newer trusted fact invalidates an obsolete witness (subject/predicate).
                fact_key = (c["subject"], c["predicate"])
                history = facts.get(fact_key, [])
                idx = bisect_right(fact_times.get(fact_key, []), event["at"]) - 1
                if idx >= 0 and (c['subject'], c['predicate'], history[idx]['at']) in conflicts:
                    fault("conflicting_authorities", f"{c['predicate']}: conflicting contemporaneous trusted records",
                          unknown=True)
                elif idx >= 0 and (history[idx]["at"], history[idx]["id"]) > (witness["at"], witness["id"]):
                    fault("stale_witness", f"{c['predicate']}: newer authoritative state supersedes witness",
                          evidence=(history[idx]["id"],))
                # Include full causal proof ancestry in the emitted certificate.
                stack = list(witness["parents"])
                while stack:
                    parent = stack.pop()
                    if parent in proof_ids:
                        continue
                    proof_ids.add(parent)
                    stack.extend(nodes[parent].get("parents", []))
            if not current_errors:
                proof_records = [nodes[k] for k in sorted(proof_ids)]
                cert = {"effect_id": event["id"], "witness_ids": sorted(proof_ids),
                        "evidence_sha256": digest(proof_records),
                        "effect_sha256": digest(event)}
                certificates.append(cert)
        verdict = "FAIL" if any(not f.unknown for f in findings) else (
            "UNVERIFIED" if findings else "PASS")
        return Result(verdict, tuple(findings), tuple(certificates), len(effects))


def minimize_witness(verifier: Verifier, trusted: list[dict], effects: list[dict],
                     target_code: str, target_effect: str) -> list[dict]:
    """Greedily minimize an effect-log failure witness (1-minimal relative to order).

    Preserves the *same finding code and effect ID*. Never modifies trusted state.
    This is not guaranteed globally smallest. The effect log must be nonempty.
    """
    work = list(effects)
    changed = True
    while changed:
        changed = False
        for i in range(len(work)):
            smaller = work[:i] + work[i + 1:]
            result = verifier.evaluate(trusted, smaller)
            if any(f.code == target_code and f.effect_id == target_effect for f in result.findings):
                work = smaller
                changed = True
                break
    return work
