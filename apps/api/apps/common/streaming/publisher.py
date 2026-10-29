"""
Thin wrapper for publishing Server-Sent Events from regular sync Django code —
views, signals, services. Mirrors `apps.document.realtime`'s channel-layer
helper, but for the SSE side: a plain Redis `PUBLISH`, independent of Django
Channels and of `apps.common.realtime`'s WebSocket dispatcher — the two transports don't
share an event bus, each domain picks the one it needs.

Channel naming mirrors the WS side's per-user group (`user-<id>`, see
`apps.common.realtime.consumers.GlobalConsumer`) so the same identity is reused across
both transports, prefixed with `stream:` to namespace the SSE pub/sub channels
from anything else on the same Redis instance.

Best-effort, no replay: `PUBLISH` only reaches subscribers connected at that exact
moment — there's no backlog, so a client that's mid-reconnect when this fires never
sees that event over the stream (the `id:` field on the SSE frame is informational,
nothing here reads a client's `Last-Event-ID` to backfill). Same philosophy as the
document WS side (see `apps.document.realtime`): treat what you push here
as a "something happened, go refetch if you care" nudge, not as the source of
truth. Only publish events whose underlying state is durable elsewhere (a DB row,
same as `Inbox` here) — if a channel is the only place an event exists, a missed
`PUBLISH` means it's gone for good.
"""

import json
import uuid

from django.conf import settings
from redis import Redis


def _channel_key(channel: str) -> str:
    return f"stream:{channel}"


def publish_event(channel: str, event: str, data: dict) -> None:
    envelope = {
        "id": str(uuid.uuid4()),
        "event": event,
        "data": data,
    }

    redis_client = Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )

    redis_client.publish(
        _channel_key(channel),
        json.dumps(envelope),
    )


def publish_to_user(user_id, event: str, data: dict) -> None:
    """Convenience for the common case — push to everything that user has open,
    same identity as the WS `user-<id>` group."""
    publish_event(f"user-{user_id}", event, data)
