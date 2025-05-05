from typing import Any

from lilya.requests import Request
from lilya.templating.controllers import TemplateController

from edgy.contrib.admin.mixins import AdminMixin
from edgy.contrib.admin.model_registry import get_registered_models


class AdminDashboard(AdminMixin, TemplateController):
    template_name = "admin/base.html"

    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:
        context = await super().get_context_data(request, **kwargs)
        context.update(
            {
                "title": "Dashboard",
            }
        )
        return context

    async def get(self, request: Request) -> Any:
        return await self.render_template(request)


class ModelListView(AdminMixin, TemplateController):
    template_name = "admin/models.html"

    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:
        context = await super().get_context_data(request, **kwargs)
        context.update({"title": "Models", "models": get_registered_models()})
        return context

    async def get(self, request: Request) -> Any:
        return await self.render_template(request)
