import json

from channels.generic.websocket import AsyncWebsocketConsumer


class GlobalConsumer(AsyncWebsocketConsumer):
    """
    Single WebSocket entrypoint for the application.

    Realtime features are multiplexed through the `type` field:

        document.subscribe
        document.acquire_lock
        presence.heartbeat
        chat.message
        notification.read

    The GlobalConsumer is responsible only for connection lifecycle and routing.
    Domain-specific behavior belongs to handlers.
    """

    HANDLER_CLASSES = tuple()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.user = None
        self.user_group = None
        self.handlers = {}

    async def connect(self):
        self.user = self.scope["user"]
        self.user_group = f"user:{self.user.id}"

        self.handlers = {handler_cls.prefix: handler_cls(self) for handler_cls in self.HANDLER_CLASSES}

        await self.accept()

        await self.channel_layer.group_add(
            self.user_group,
            self.channel_name,
        )

        for handler in self.handlers.values():
            await handler.on_connect()

    async def disconnect(self, close_code):
        for handler in self.handlers.values():
            await handler.on_disconnect()

        if self.user and self.user.is_authenticated:
            await self.channel_layer.group_discard(
                self.user_group,
                self.channel_name,
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (TypeError, json.JSONDecodeError):
            return

        if not isinstance(data, dict):
            return

        handler = self._handler_for(data.get("type"))

        if handler:
            await handler.receive(data)

    async def dispatch(self, message):
        handler = self._handler_for(message.get("type"))

        if handler:
            await handler.dispatch(message)
            return

        await super().dispatch(message)

    def _handler_for(self, event_type: str | None):
        if not event_type or "." not in event_type:
            return None

        prefix, _ = event_type.split(".", 1)

        return self.handlers.get(prefix)
