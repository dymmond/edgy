from typing import Any
import edgy
from edgy.conf import settings
from lilya.apps import Lilya
from lilya.middleware import DefineMiddleware
from lilya.middleware.sessions import SessionMiddleware
from lilya.routing import Include
from edgy.contrib.admin import create_admin_app

models = edgy.Registry(
    database="...",
)


class User(edgy.Model):
    username: str = edgy.fields.CharField(max_length=100, unique=True)
    active: bool = edgy.fields.BooleanField(default=False)


def get_application() -> Any:
    admin_app = create_admin_app()
    routes = [
        Include(
            path=settings.admin_config.admin_prefix_url,
            app=admin_app,
            middleware=[
                DefineMiddleware(
                    SessionMiddleware,
                    secret_key=settings.admin_config.SECRET_KEY,
                    session_cookie="admin_session",
                ),
            ],
        ),
    ]
    app: Any = Lilya(
        routes=routes,
    )
    app = models.asgi(app)
    edgy.monkay.set_instance(edgy.Instance(registry=models, app=app))
    return app


application = get_application()
