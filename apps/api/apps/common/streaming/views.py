import json

import redis.asyncio as aioredis
from django.conf import settings
from django.http import HttpRequest, HttpResponseForbidden, StreamingHttpResponse

from shared.enums import MimeType
from shared.renderers.sse import SSERenderer

HEARTBEAT_SECONDS = 15
"""How often a keep-alive comment is sent when no event arrives, so proxies/load
balancers with an idle-connection timeout (nginx defaults to 60s) don't kill the
stream. Well under that default, mirrors the spirit of the WS lock's heartbeat."""


async def stream_view(request: HttpRequest):
    """Generic per-user stream, `GET /stream/`. A domain that needs its own
    channel scoping (workplace, document, ...) doesn't use this endpoint — it
    builds its own response with `sse_response()` on a channel name it owns and
    authorizes itself (see `apps.inbox.views.inbox.InboxViewSet.sse`)."""
    user = await request.auser()

    if not user.is_authenticated:
        return HttpResponseForbidden()

    return sse_response(f"user-{user.id}")


def sse_response(channel: str) -> StreamingHttpResponse:
    """Wires up the transport (headers, content type, the event generator) for an
    SSE channel. `channel` is the bare name, no `stream:` prefix — see
    `apps.common.streaming.publisher`. Callers own their own channel naming and
    authorization; this only builds the response."""
    response = StreamingHttpResponse(
        event_stream(channel),
        content_type=MimeType.SSE,
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"

    return response


async def event_stream(channel: str):
    renderer = SSERenderer()
    client = aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
    )
    pubsub = client.pubsub()

    try:
        await pubsub.subscribe(f"stream:{channel}")

        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True,
                timeout=HEARTBEAT_SECONDS,
            )

            if message is None:
                yield b": keep-alive\n\n"
                continue

            envelope = json.loads(message["data"])

            yield await renderer.render(envelope)

    finally:
        await pubsub.unsubscribe(f"stream:{channel}")
        await pubsub.aclose()
        await client.aclose()
