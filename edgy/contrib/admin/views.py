from typing import Any

from lilya.exceptions import NotFound
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


class ModelDetailView(AdminMixin, TemplateController):
    template_name = "admin/model_detail.html"

    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:
        context = await super().get_context_data(request, **kwargs)
        model_name = request.path_params.get("name")

        models = get_registered_models()
        model = models.get(model_name)
        if not model:
            raise NotFound()

        # Fetch first 100 records (for now) from model
        objects = await model.query.limit(100).all()

        context.update({
            "title": model.__name__,
            "model": model,
            "objects": objects,
            "model_name": model_name
        })
        return context

    async def get(self, request: Request, **kwargs: Any) -> Any:
        return await self.render_template(request, **kwargs)
