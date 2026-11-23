"""Fully fictional, deterministic cross-domain CAPE-Graph fixtures.

These are author-side examples; official PALE authorization and grading must be
issued by its service layer, not the developer's synthetic fixtures.
"""
from __future__ import annotations
from copy import deepcopy
from .core import Rule, Verifier


def fact(id: str, at: int, issuer: str, subject: str, predicate: str,
         value: object, parents: list[str] | None = None) -> dict:
    return dict(id=id, type="fact", at=at, issuer=issuer, subject=subject,
                predicate=predicate, value=value, parents=parents or [])


def grant(id: str, at: int, issuer: str, principal: str, action: str,
          scope: str, not_after: int = 200) -> dict:
    return dict(id=id, type="grant", at=at, issuer=issuer, principal=principal,
                action=action, scope=scope, not_after=not_after)


def claim(predicate: str, subject: str, value: object, witness: str) -> dict:
    return dict(predicate=predicate, subject=subject, value=value, witness=witness)


def effect(id: str, at: int, action: str, scope: str,
           claims: list[dict], grant_id: str, idem: str = "") -> dict:
    return dict(id=id, at=at, principal="agent", action=action,
                scope=scope, claims=claims, grant_id=grant_id,
                idempotency_key=idem)


def policy() -> Verifier:
    r = {
        "publish_release": Rule("publish_release",
            (("release_state", "published"), ("signature_state", "verified"),
             ("credit_state", "accepted")),
            frozenset({"release_state", "signature_state", "credit_state"}),
            scope_bound=frozenset({"release_state", "signature_state"})),
        "merge_notice": Rule("merge_notice", (("merge_state", "merged"),),
            frozenset({"merge_state"}), scope_bound=frozenset({"merge_state"})),
        "submit_report": Rule("submit_report",
            (("cpu_status", "success"), ("holdout", "frozen_nine"),
             ("gpu_status", "not_executed")),
            frozenset({"cpu_status", "holdout", "gpu_status"})),
        "deliver_item": Rule("deliver_item",
            (("consent", "accepted"), ("route", "step_free"),
             ("delivery", "confirmed")),
            frozenset({"consent", "route", "delivery"}),
            scope_bound=frozenset({"consent", "route", "delivery"})),
    }
    issuers = {
        "release_state": {"registry"}, "signature_state": {"signer"},
        "credit_state": {"ledger"}, "merge_state": {"code_host"},
        "cpu_status": {"scheduler"}, "holdout": {"protocol_ledger"},
        "gpu_status": {"scheduler"}, "consent": {"volunteer_service"},
        "route": {"facilities"}, "delivery": {"dispatch"},
    }
    return Verifier(r, issuers, {"owner", "coordinator", "researcher"})


def cases() -> dict[str, tuple[list[dict], list[dict]]]:
    # Timesteps model the simulation clock, not dates from a real service.
    release_t = [
        grant("g_final", 5, "owner", "agent", "publish_release", "release:2.1.0"),
        fact("fix_merged", 10, "code_host", "release:2.1.0", "merge_state", "merged"),
        fact("release_published", 40, "registry", "release:2.1.0", "release_state", "published", ["fix_merged"]),
        fact("signed_assets", 42, "signer", "release:2.1.0", "signature_state", "verified", ["release_published"]),
        fact("canonical_credit", 43, "ledger", "person:avery", "credit_state", "accepted"),
    ]
    release_e = [effect("cms_1", 50, "publish_release", "release:2.1.0", [
        claim("release_state", "release:2.1.0", "published", "release_published"),
        claim("signature_state", "release:2.1.0", "verified", "signed_assets"),
        claim("credit_state", "person:avery", "accepted", "canonical_credit"),
    ], "g_final", "cms-key-1")]
    lab_t = [
        grant("g_report", 5, "researcher", "agent", "submit_report", "lab:packet"),
        fact("protocol", 4, "protocol_ledger", "lab:protocol", "holdout", "frozen_nine"),
        fact("gpu_off", 21, "scheduler", "lab:quota", "gpu_status", "not_executed"),
        fact("cpu_receipt", 28, "scheduler", "lab:cpu-job", "cpu_status", "success", ["protocol"]),
    ]
    lab_e = [effect("report_1", 35, "submit_report", "lab:packet", [
        claim("cpu_status", "lab:cpu-job", "success", "cpu_receipt"),
        claim("holdout", "lab:protocol", "frozen_nine", "protocol"),
        claim("gpu_status", "lab:quota", "not_executed", "gpu_off"),
    ], "g_report", "packet-1")]
    delivery_t = [
        grant("g_delivery", 4, "coordinator", "agent", "deliver_item", "item:C"),
        fact("lift_closed", 10, "facilities", "route:east", "route", "unavailable"),
        fact("step_free_route", 12, "facilities", "item:C", "route", "step_free", ["lift_closed"]),
        fact("rowan_accept", 25, "volunteer_service", "item:C", "consent", "accepted"),
        fact("receipt_C", 32, "dispatch", "item:C", "delivery", "confirmed", ["rowan_accept", "step_free_route"]),
    ]
    delivery_e = [effect("dispatch_C", 35, "deliver_item", "item:C", [
        claim("consent", "item:C", "accepted", "rowan_accept"),
        claim("route", "item:C", "step_free", "step_free_route"),
        claim("delivery", "item:C", "confirmed", "receipt_C"),
    ], "g_delivery", "delivery-C")]
    return {"release": (release_t, release_e), "lab": (lab_t, lab_e),
            "delivery": (delivery_t, delivery_e)}


def personalized_notice(allow_merge_only: bool) -> tuple[list[dict], list[dict]]:
    """Hold all current request and world facts fixed; vary prior authorization."""
    trusted, _ = cases()["release"]
    trusted = deepcopy(trusted)
    if allow_merge_only:
        trusted.append(grant("g_early", 1, "owner",
                             "agent", "merge_notice", "release:2.1.0", not_after=40))
    action = effect("notice_early", 18, "merge_notice", "release:2.1.0", [
        claim("merge_state", "release:2.1.0", "merged", "fix_merged")
    ], "g_early", "notice-1")
    return trusted, [action]
