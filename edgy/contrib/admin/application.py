from __future__ import annotations

from typing import Any

from lilya.apps import Lilya
from lilya.requests import Request
from lilya.routing import Include, RoutePath
from lilya.templating.controllers import templates  # noqa

from edgy.conf import settings
from edgy.contrib.admin.views import (
    AdminDashboard,
    ModelCreateView,
    ModelDeleteView,
    ModelDetailView,
    ModelEditView,
    ModelListView,
    ModelObjectView,
)


async def not_found(request: Request, exc: Exception) -> Any:
    return templates.get_template_response(
        request,
        "404.html",
        context={"title": "Not Found"},
    )


app = Lilya(
    debug=True,
    routes=[
        Include(
            path=settings.admin_config.admin_prefix_url,
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
        ),
    ],
    exception_handlers={404: not_found},
)
