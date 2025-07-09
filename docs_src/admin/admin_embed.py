from typing import Any
import edgy
from edgy.conf import settings
from lilya.context import request_context
from lilya.apps import Lilya
from lilya.middleware import DefineMiddleware
from lilya.requests import Connection
from lilya.authentication import AuthenticationBackend, AuthCredentials, UserInterface, AuthResult
from lilya.middleware.sessions import SessionMiddleware
from lilya.middleware.session_context import SessionContextMiddleware
from lilya.middleware.authentication import AuthenticationMiddleware
from lilya.middleware.request_context import RequestContextMiddleware
from lilya.routing import Include
from edgy.contrib.admin import create_admin_app

models = edgy.Registry(
    database="...",
)


class User(UserInterface, edgy.Model):
    username: str = edgy.fields.CharField(max_length=100, unique=True)
    active: bool = edgy.fields.BooleanField(default=False)


def get_application() -> Any:
    admin_app = create_admin_app()
    # or with lilya 0.15.5
    # admin_app = create_admin_app(session_sub_path="admin")
    routes = [
        Include(
            # you can use a path you want. By default the admin_prefix_url is automatically inferred.
            # Note: in case of a reverse proxy with script path make sure to provide a
            # value for settings.admin_config.admin_prefix_url which includes the path under which the app is hosted (if not /)
            path="/admin",
            app=admin_app,
        ),
    ]
    app: Any = Lilya(
        routes=routes,
        middleware=[
            # you can also use a different secret_key aside from settings.admin_config.SECRET_KEY
            DefineMiddleware(SessionMiddleware, secret_key=settings.admin_config.SECRET_KEY),
        ],
    )
    app = models.asgi(app)
    edgy.monkay.set_instance(edgy.Instance(registry=models, app=app))
    return app


application = get_application()
