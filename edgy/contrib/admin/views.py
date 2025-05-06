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
    """
    View for the administration dashboard page.
    """
    template_name = "admin/base.html"

    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:
        """
        Prepares the context data for the dashboard template.

        Args:
            request: The incoming Starlette Request object.
            **kwargs: Additional keyword arguments.

        Returns:
            A dictionary containing context data, including the page title.
        """
        context = await super().get_context_data(request, **kwargs)
        context.update(
            {
                "title": "Dashboard",
            }
        )
        return context

    async def get(self, request: Request) -> Any:
        """
        Handles GET requests for the administration dashboard page.

        Args:
            request: The incoming Starlette Request object.

        Returns:
            The rendered template response for the dashboard.
        """
        return await self.render_template(request)


class ModelListView(AdminMixin, TemplateController):
    """
    View for listing all registered models in the admin interface.
    """
    template_name = "admin/models.html"

    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:
        """
        Prepares the context data for the models list template.

        Retrieves all registered models and adds them to the context.

        Args:
            request: The incoming Starlette Request object.
            **kwargs: Additional keyword arguments.

        Returns:
            A dictionary containing context data, including the page title
            and a list of registered models.
        """
        context = await super().get_context_data(request, **kwargs)
        context.update({"title": "Models", "models": get_registered_models()})
        return context

    async def get(self, request: Request) -> Any:
        """
        Handles GET requests for the registered models list page.

        Args:
            request: The incoming Starlette Request object.

        Returns:
            The rendered template response for the models list.
        """
        return await self.render_template(request)


class ModelDetailView(AdminMixin, TemplateController):
    """
    View for displaying details of a specific model, typically listing its objects.
    """
    template_name = "admin/model_detail.html"

    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:
        """
        Prepares the context data for the model detail template.

        Retrieves the model name from the request, finds the corresponding
        model class, fetches a limited number of objects for that model,
        and adds them to the context.

        Args:
            request: The incoming Starlette Request object.
            **kwargs: Additional keyword arguments from the path parameters.

        Returns:
            A dictionary containing context data, including the model name,
            the model class, and a list of objects belonging to the model.

        Raises:
            NotFound: If the model name is not found in the registered models.
        """
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
        """
        Handles GET requests for the model detail page.

        Renders the template configured for this view, populated with
        context data prepared by `get_context_data`.

        Args:
            request: The incoming Starlette Request object.
            **kwargs: Additional keyword arguments from the path parameters.

        Returns:
            The rendered template response for the model detail page.
        """
        return await self.render_template(request, **kwargs)

    async def post(self, request: Request, **kwargs: Any) -> Any:
        """
        Handles POST requests for the page.

        Currently, this method just re-renders the template, implying
        that saving/processing the POST data is handled elsewhere or not implemented here.

        Args:
            request: The incoming Starlette Request object.
            **kwargs: Additional keyword arguments from the path parameters.

        Returns:
            The rendered template response for the page.
        """
        return await self.render_template(request, **kwargs)


class BaseObjectView:
    """
    Base class for admin views that operate on a single model object.
    Provides utility methods for extracting and parsing object IDs.
    """

    def get_object_id(self, request: Request) -> int:
        """
        Extracts the object ID from the request's path parameters.

        Assumes the object ID is present in the path parameters under the key "id".

        Args:
            request: The incoming Starlette Request object.

        Returns:
            The object ID as an integer.
        """
        return int(request.path_params.get("id"))

    def parse_object_id(self, obj_id: str | int) -> int:
        """
        Parses a string or integer object ID into an integer.

        Ensures the ID is in integer format.

        Args:
            obj_id: The object ID, which can be a string or an integer.

        Returns:
            The object ID as an integer.
        """
        if isinstance(obj_id, str):
            return int(obj_id)
        return obj_id

class ModelObjectView(AdminMixin, BaseObjectView, TemplateController):
    """
    View for displaying the details of a single object of a specific model.
    """
    template_name = "admin/model_object.html"

    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:
        """
        Prepares the context data for the model object detail template.

        Retrieves the model name and object ID from the request, finds the
        corresponding model and fetches the specific instance by its ID.
        Adds the instance, model information, and title to the context.

        Args:
            request: The incoming Starlette Request object.
            **kwargs: Additional keyword arguments from the path parameters.

        Returns:
            A dictionary containing context data, including the page title,
            the model instance, the model class, and the model name.

        Raises:
            NotFound: If the model name or the specific instance is not found.
        """
        context = await super().get_context_data(request, **kwargs) # noqa
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
        """
        Handles GET requests for the model object detail page.

        Renders the template configured for this view, populated with
        context data prepared by `get_context_data`.

        Args:
            request: The incoming Starlette Request object.
            **kwargs: Additional keyword arguments from the path parameters.

        Returns:
            The rendered template response for the object detail page.
        """
        return await self.render_template(request, **kwargs)

    async def post(self, request: Request, **kwargs: Any) -> Any:
        """
        Handles POST requests for the model object detail page.

        Currently, this method just re-renders the template, implying
        that saving/editing is handled elsewhere or not implemented here.

        Args:
            request: The incoming Starlette Request object.
            **kwargs: Additional keyword arguments from the path parameters.

        Returns:
            The rendered template response for the object detail page.
        """
        return await self.render_template(request, **kwargs)

class ModelEditView(AdminMixin, BaseObjectView, TemplateController):
    template_name = "admin/model_edit.html"

    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:
        """
        Prepares the context data for the model edit template.

        Retrieves the model name and object ID from the request, fetches
        the corresponding model and instance, and populates the context
        dictionary with information needed for rendering the edit form.

        Args:
            request: The incoming Starlette Request object.
            **kwargs: Additional keyword arguments from the path parameters.

        Returns:
            A dictionary containing context data for the template, including
            the page title, the model instance, the model class, and the model name.

        Raises:
            NotFound: If the model name or the specific instance is not found.
        """
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
        """
        Handles GET requests to display the model edit form.

        Renders the template configured for this view, populated with
        context data prepared by `get_context_data`.

        Args:
            request: The incoming Starlette Request object.
            **kwargs: Additional keyword arguments from the path parameters.

        Returns:
            The rendered template response containing the edit form.
        """
        return await self.render_template(request, **kwargs)

    async def get_model_from_foreign_key(self, model_name: str, obj_id: int):
        """
        Gets the object from the foreign key field.
        then queries the database for the object with the given id.

        Args:
            model_name: The name of the related model.
            obj_id: The ID of the related object.

        Returns:
            The instance of the related model.

        Raises:
            NotFound: If the model or object is not found.
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
        """
        Handles POST requests to save the changes to a model instance.

        Retrieves the model name, object ID, and form data from the request,
        finds the corresponding model and instance, updates the instance
        using the form data via `save_model`, and redirects the user back
        to the edited object's detail page.

        Args:
            request: The incoming Starlette Request object.
            **kwargs: Additional keyword arguments from the path parameters.

        Returns:
            A RedirectResponse to the edited object's detail page after saving.

        Raises:
            NotFound: If the model name or the specific instance is not found.
        """
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


class ModelDeleteView(AdminMixin, BaseObjectView, TemplateController):
    template_name = "admin/model_edit.html"

    async def post(self, request: Request, **kwargs: Any) -> RedirectResponse:
        """
        Handles POST requests to delete a model instance.

        Retrieves the model name and object ID from the request's path parameters,
        finds the corresponding model and instance using the object ID,
        deletes the instance from the database, and redirects the user back
        to the model's listing page.

        Args:
            request: The incoming Starlette Request object.
            **kwargs: Additional keyword arguments from the path parameters.

        Returns:
            A RedirectResponse to the model's listing page after deletion.

        Raises:
            NotFound: If the model name or the specific instance is not found.
        """
        model_name = request.path_params.get("name")

        models = get_registered_models()
        model = models.get(model_name)
        if not model:
            raise NotFound()

        instance = await model.query.get(id=self.get_object_id(request))
        if not instance:
            raise NotFound()

        await instance.delete()
        return RedirectResponse(f"{settings.admin_config.admin_prefix_url}/models/{model_name}")
