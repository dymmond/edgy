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
    is_admin: bool = edgy.fields.BooleanField(default=False)
    # we still need an authenticating backend checking the pw
    pw: str = edgy.fields.PasswordField()

    class Meta:
        registry = models

    @classmethod
    def get_admin_marshall_config(cls, *, phase: str, for_schema: bool) -> dict:
        exclude = []
        # Works only when embedding, by default we have no request.user.and request_context
        user = request_context.user
        if not user.is_authenticated or not user.is_admin:
            exclude.append("is_admin")
            if phase == "update":
                exclude.append("name")

        return {"exclude": exclude}


class SessionBackend(AuthenticationBackend):
    async def authenticate(self, connection: Connection) -> AuthResult | None:
        if not connection.scope["session"].get("username", None):
            return None
        user = await User.query.get(username=connection.scope["session"]["username"])
        if user:
            return AuthCredentials(["authenticated"]), user
        return None


def get_application() -> Any:
    admin_app = create_admin_app()
    # or with lilya 0.15.5
    # admin_app = create_admin_app(session_sub_path="admin")
    routes = [
        Include(
            # provide the path explicit
            path="/admin",
            # using admin_prefix_url won't work behind reverse proxies
            app=admin_app,
        ),
    ]
    app: Any = Lilya(
        routes=routes,
        middleware=[
            # you can also use a different secret_key aside from settings.admin_config.SECRET_KEY
            DefineMiddleware(SessionMiddleware, secret_key=settings.admin_config.SECRET_KEY),
            DefineMiddleware(SessionContextMiddleware),
            DefineMiddleware(AuthenticationMiddleware, backend=[SessionBackend]),
            DefineMiddleware(RequestContextMiddleware),
        ],
    )
    app = models.asgi(app)
    edgy.monkay.set_instance(edgy.Instance(registry=models, app=app))
    return app


application = get_application()
