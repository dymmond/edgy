from __future__ import annotations

from typing import Any

from lilya.apps import Lilya
from lilya.requests import Request
from lilya.routing import Include, RoutePath
from lilya.templating.controllers import templates  # noqa

from edgy.conf import settings
from edgy.contrib.admin.views import AdminDashboard, ModelDetailView, ModelListView


async def not_found(request: Request, exc: Exception) -> Any:
    return templates.get_template_response(
        request,
        "404.html",
        context={"title": "Not Found"},
    )


app = Lilya(
    routes=[
        Include(
            path=settings.admin_config.admin_prefix_url,
            routes=[
                RoutePath("/", handler=AdminDashboard, name="admin"),
                RoutePath("/models", handler=ModelListView, name="models"),
                RoutePath("/models/{name}", handler=ModelDetailView, name="model-details"),
            ],
        ),
    ],
    exception_handlers={404: not_found},
)


# class EdgyAdmin:
#     def __init__(self, app: Lilya, templates_dir: str = "templates") -> None: # noqa
#         self.app = app
#         self.templates_dir= templates_dir,
#         self.__init_templating_engine()
#         self.__add_base_controllers()
#
#     def __init_templating_engine(self) -> Jinja2Template:
#         templates = Jinja2Template("templates")
#         loaders = [
#             FileSystemLoader(self.templates_dir),
#             PackageLoader("edgy.contrib.admin", "templates"),
#         ]
#
#         templates.env.loader = ChoiceLoader(loaders)
#         templates.env.globals["min"] = min
#         templates.env.globals["zip"] = zip
#         templates.env.globals["admin"] = self
#         templates.env.globals["is_list"] = lambda x: isinstance(x, list)
#
#         return templates
#
#     def __add_base_controllers(self) -> None:
#         breakpoint()
#         self.app.router.routes.extend(app.router.routes)
#         self.app.add_exception_handler(404, not_found)
#
#     def add_model(self, model: Any) -> None: # noqa
#         register_model(model)
