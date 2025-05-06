from __future__ import annotations

from typing import Any

from lilya.datastructures import FormData
from lilya.exceptions import NotFound  # noqa
from lilya.requests import Request
from lilya.responses import RedirectResponse
from lilya.templating.controllers import TemplateController

import edgy
from edgy.conf import settings
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


class BaseObjectView:

    def get_object_id(self, request: Request) -> int:
        return int(request.path_params.get("id"))

    def parse_object_id(self, obj_id: str | int) -> int:
        if isinstance(obj_id, str):
            return int(obj_id)
        return obj_id

class ModelObjectView(AdminMixin, BaseObjectView, TemplateController):
    template_name = "admin/model_object.html"

    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:
        context = await super().get_context_data(request, **kwargs)
        model_name = request.path_params.get("name")
        obj_id = request.path_params.get("id")

        models = get_registered_models()
        model = models.get(model_name)
        if not model:
            raise NotFound()

        instance = await model.query.get_or_none(id=self.get_object_id(request))
        if not instance:
            raise NotFound()

        context.update({
            "title": f"{model_name.capitalize()} #{obj_id}",
            "object": instance,
            "model": model,
            "model_name": model_name,
        })
        return context

    async def get(self, request: Request, **kwargs: Any) -> Any:
        return await self.render_template(request, **kwargs)

    async def post(self, request: Request, **kwargs: Any) -> Any:
        return await self.render_template(request, **kwargs)

class ModelEditView(AdminMixin, BaseObjectView, TemplateController):
    template_name = "admin/model_edit.html"

    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:
        context = await super().get_context_data(request, **kwargs)
        model_name = request.path_params.get("name")
        obj_id = request.path_params.get("id")

        models = get_registered_models()
        model = models.get(model_name)

        if not model:
            raise NotFound()

        instance = await model.query.get(id=self.get_object_id(request))
        if not instance:
            raise NotFound()

        context.update({
            "title": f"Edit {model_name.capitalize()} #{obj_id}",
            "object": instance,
            "model": model,
            "model_name": model_name,
        })
        return context

    async def get(self, request: Request, **kwargs: Any) -> Any:
        return await self.render_template(request, **kwargs)

    async def get_model_from_foreign_key(self, model_name: str, obj_id: int):
        """
        Gets the object from the foreign key field.
        then queries the database for the object with the given id.
        """
        models: dict[str, Any] = get_registered_models()
        model: edgy.Model = models.get(model_name)

        if not model:
            raise NotFound()

        instance = await model.query.get(id=self.parse_object_id(obj_id))
        if not instance:
            raise NotFound()
        return instance

    async def save_model(self, instance: type[edgy.Model], form_data: FormData):
        """
        Saves an Edgy model instance based on form data.

        This function updates the fields of a given Edgy model instance
        using data from a FormData object. It specifically handles foreign key
        fields by fetching the related model instance before updating.
        Finally, it saves the updated model instance.

        Args:
            instance: The Edgy model instance to be updated and saved.
                      Note: The type hint 'type[edgy.Model]' might be intended
                      as the instance itself, not the class type.
            form_data: A FormData object containing the data to update the model.
        """
        # Update fields
        form_to_dict = {k: v for k, v in form_data.items() if k not in ["pk", "id"]}

        # Make sure if one of the fields is not a primary key
        data: dict[str, Any] = {}
        for key, value in form_to_dict.items():
            if key in instance.meta.foreign_key_fields:
                attribute = instance.meta.fields.get(key)

                # Check if its a ManyToMany field
                if not attribute.is_m2m:
                    data[key] = await self.get_model_from_foreign_key(key, self.parse_object_id(value))
            else:
                data[key] = value

        await instance.update(**data)
        await instance.save()


    async def post(self, request: Request, **kwargs: Any) -> RedirectResponse:
        model_name = request.path_params.get("name")
        obj_id = request.path_params.get("id")
        form_data = await request.form()

        models = get_registered_models()
        model = models.get(model_name)

        if not model:
            raise NotFound()

        instance = await model.query.get(id=self.get_object_id(request))
        if not instance:
            raise NotFound()


        await self.save_model(instance, form_data)
        return RedirectResponse(f"{settings.admin_config.admin_prefix_url}/models/{model_name}/{obj_id}")
