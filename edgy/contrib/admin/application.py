from __future__ import annotations

from pathlib import Path
from typing import Any

from lilya.apps import ChildLilya
from lilya.requests import Request
from lilya.routing import RoutePath
from lilya.templating import Jinja2Template

from edgy.contrib.admin.views import (
    AdminDashboard,
    ModelCreateView,
    ModelDeleteView,
    ModelDetailView,
    ModelEditView,
    ModelListView,
    ModelObjectView,
)

template_directory = Path(__file__).parent / "templates"
templates = Jinja2Template(directory=template_directory)


async def not_found(request: Request, exc: Exception) -> Any:
    return templates.get_template_response(
        request,
        "404.html",
        context={"title": "Not Found"},
    )


app = ChildLilya(
    debug=True,
    routes=[
        RoutePath("/", handler=AdminDashboard, name="admin"),
        RoutePath("/models", handler=ModelListView, name="models"),
        RoutePath("/models/{name}", handler=ModelDetailView, name="model-details"),
        RoutePath("/models/{name}/create", handler=ModelCreateView, name="model-create"),
        RoutePath("/models/{name}/{id}", handler=ModelObjectView, name="model-object"),
        RoutePath(
            "/models/{name}/{id}/edit",
            handler=ModelEditView,
            name="model-edit",
            methods=["GET", "POST"],
        ),
        RoutePath(
            "/models/{name}/{id}/delete",
            handler=ModelDeleteView,
            name="model-delete",
            methods=["POST"],
        ),
    ],
    exception_handlers={404: not_found},
)
