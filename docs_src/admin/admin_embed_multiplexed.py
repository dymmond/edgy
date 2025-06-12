from typing import Any
import edgy
from edgy.conf import settings
from lilya.apps import Lilya
from lilya.middleware import DefineMiddleware
from lilya.middleware.sessions import SessionMiddleware
from lilya.middleware.session_context import SessionContextMiddleware
from lilya.routing import Include
from edgy.contrib.admin import create_admin_app

models = edgy.Registry(
    database="...",
)


class User(edgy.Model):
    username: str = edgy.fields.CharField(max_length=100, unique=True)
    active: bool = edgy.fields.BooleanField(default=False)


def get_application() -> Any:
    # multiplexed with lilya 0.15.5
    admin_app = create_admin_app(session_sub_path="admin")
    routes = [
        Include(
            path=settings.admin_config.admin_prefix_url,
            app=admin_app,
        ),
    ]
    app: Any = Lilya(
        routes=routes,
        middleware=[
            # you can also use a different secret_key aside from settings.admin_config.SECRET_KEY
            DefineMiddleware(SessionMiddleware, secret_key=settings.admin_config.SECRET_KEY),
            DefineMiddleware(SessionContextMiddleware),
        ],
    )
    app = models.asgi(app)
    edgy.monkay.set_instance(edgy.Instance(registry=models, app=app))
    return app


application = get_application()
