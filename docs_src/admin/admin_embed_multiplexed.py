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

models1 = edgy.Registry(
    database="...",
)

models2 = edgy.Registry(
    database="...",
)


class MyModel1(edgy.Model):
    name: str = edgy.fields.CharField(max_length=100, unique=True)

    class Meta:
        registry = models1


class MyModel2(edgy.Model):
    name: str = edgy.fields.CharField(max_length=100, unique=True)

    class Meta:
        registry = models2


def get_application() -> Any:
    admin_app1 = create_admin_app(session_sub_path="admin1", registry=models1)
    admin_app2 = create_admin_app(session_sub_path="admin2", registry=models2)
    routes = [
        Include(
            path="/admin1",
            app=admin_app1,
        ),
        Include(
            path="/admin2",
            app=admin_app2,
        ),
    ]
    app: Any = Lilya(
        routes=routes,
        middleware=[
            # you can also use a different secret_key aside from settings.admin_config.SECRET_KEY
            DefineMiddleware(SessionMiddleware, secret_key=settings.admin_config.SECRET_KEY),
            # the session context for the global app (optional)
            DefineMiddleware(SessionContextMiddleware),
        ],
    )
    # models, a complete different registry is used globally (optional)
    app = models.asgi(app)
    edgy.monkay.set_instance(edgy.Instance(registry=models, app=app))
    return app


application = get_application()
