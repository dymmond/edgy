from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from lilya import status
from lilya.apps import ChildLilya, Lilya
from lilya.middleware import DefineMiddleware
from lilya.middleware.session_context import SessionContextMiddleware
from lilya.requests import Request
from lilya.routing import RoutePath
from lilya.templating import Jinja2Template

from edgy.contrib.lilya.middleware import EdgyMiddleware

from .views import (
    AdminDashboard,
    JSONSchemaView,
    ModelDetailView,
    ModelObjectCreateView,
    ModelObjectDeleteView,
    ModelObjectDetailView,
    ModelObjectEditView,
    ModelOverview,
)

if TYPE_CHECKING:
    from edgy.conf.global_settings import EdgySettings
    from edgy.core.connection import Registry

templates = Jinja2Template(directory=str(Path(__file__).resolve().parent / "templates"))
templates.env.globals["getattr"] = getattr


async def not_found(request: Request, exc: Exception) -> Any:
    return templates.get_template_response(
        request, "404.html", context={"title": "Not Found"}, status_code=status.HTTP_404_NOT_FOUND
    )


def create_admin_app(
    *,
    session_sub_path: str = "",
    registry: Registry | None = None,
    settings: EdgySettings | None = None,
) -> Lilya:
    middleware: list[DefineMiddleware] = [
        DefineMiddleware(EdgyMiddleware, registry=registry, settings=settings),
        DefineMiddleware(SessionContextMiddleware, sub_path=session_sub_path),
    ]
    return ChildLilya(
        routes=[
            RoutePath("/", handler=AdminDashboard, name="admin"),
            RoutePath("/models", handler=ModelOverview, name="models"),
            RoutePath("/models/{name}", handler=ModelDetailView, name="model-details"),
            RoutePath("/models/{name}/json", handler=JSONSchemaView, name="model-schema"),
            RoutePath("/models/{name}/create", handler=ModelObjectCreateView, name="model-create"),
            RoutePath("/models/{name}/{id}", handler=ModelObjectDetailView, name="model-object"),
            RoutePath(
                "/models/{name}/{id}/edit",
                handler=ModelObjectEditView,
                name="model-edit",
                methods=["GET", "POST"],
            ),
            RoutePath(
                "/models/{name}/{id}/delete",
                handler=ModelObjectDeleteView,
                name="model-delete",
                methods=["POST"],
            ),
        ],
        middleware=middleware,
        exception_handlers={404: not_found},
    )
