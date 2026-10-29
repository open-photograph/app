import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application
from django.urls import re_path

from apps.common.websocket.consumers import GlobalConsumer

os.environ.setdefault(
    key="DJANGO_SETTINGS_MODULE",
    value="config.settings",
)

django_asgi_app = get_asgi_application()

router = [
    re_path(r"^api/ws/$", GlobalConsumer.as_asgi()),
    re_path(r"^api/ws/(?P<room_name>[^/]+)/$", GlobalConsumer.as_asgi()),
]

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(router)),
        ),
    }
)
