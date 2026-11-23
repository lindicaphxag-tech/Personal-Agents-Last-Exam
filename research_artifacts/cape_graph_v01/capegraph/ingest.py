"""Service-side-only ingestion contract for CAPE-Graph.

Caller MUST acquire these channel streams from an authenticated, isolated PALE
Infra/Messaging/issuer interface, not from a candidate agent transcript.

This is a design-compatible *prototype adapter*, not a verified integration
with PALE's actual task runner (not yet released on main as of Nov 24 2026).
"""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from .core import TRUSTED_FIELDS, EFFECT_FIELDS, _exact


def ingest_service_streams(*, trusted_channels: Mapping[str, Sequence[dict]],
                           effect_channels: Mapping[str, Sequence[dict]],
                           allowed_fact_channels: set[str],
                           allowed_effect_channels: set[str]) -> tuple[list[dict], list[dict]]:
    """Bind issuer by trusted channel identity, never a self-reported field.

    A malicious agent-authored tool response MUST NEVER be routed through
    trusted_channels or effect_channels by an upstream caller.
    """
    trusted: list[dict] = []
    effects: list[dict] = []
    if set(trusted_channels) - allowed_fact_channels:
        raise ValueError('unapproved trusted provenance channel')
    if set(effect_channels) - allowed_effect_channels:
        raise ValueError('unapproved committed effect channel')
    for verified_channel, records in sorted(trusted_channels.items()):
        for i, event in enumerate(records):
            if not isinstance(event,dict) or event.get('type') not in TRUSTED_FIELDS:
                raise ValueError('unrecognized issuer event')
            if 'issuer' in event:
                raise ValueError('issuer cannot be asserted in a source event')
            _exact(event, TRUSTED_FIELDS[event['type']] - {'issuer'},f'{verified_channel}/{i}')
            trusted.append(dict(event, issuer=verified_channel))
    for verified_channel, records in sorted(effect_channels.items()):
        for i, event in enumerate(records):
            _exact(event,EFFECT_FIELDS,f'{verified_channel}/{i}')
            effects.append(dict(event))
    return trusted, effects
