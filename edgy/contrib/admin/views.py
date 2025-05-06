from __future__ import annotations

from math import ceil
from typing import Any, cast

import anyio
from lilya.datastructures import FormData
from lilya.exceptions import NotFound  # noqa
from lilya.requests import Request
from lilya.responses import RedirectResponse
from lilya.templating.controllers import TemplateController

import edgy
from edgy.conf import settings
from edgy.contrib.admin.mixins import AdminMixin
from edgy.contrib.admin.model_registry import get_registered_models
from edgy.core.db.relationships.related_field import RelatedField


class AdminDashboard(AdminMixin, TemplateController):
    """
    View for the administration dashboard page.
    """

    template_name = "admin/dashboard.html"

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

        models = get_registered_models()
        model_stats: list[dict] = []

        async with anyio.create_task_group() as tg:
            for name, model in models.items():
                tg.start_soon(self._add_model_stat, model_stats, name, model)  # type: ignore

        total_records = sum(m["count"] for m in model_stats)
        top_model = max(
            model_stats, key=lambda m: m["count"], default={"verbose": "N/A", "count": 0}
        )

        context.update(
            {
                "title": "Dashboard",
                "models": sorted(model_stats, key=lambda m: m["verbose"]),
                "total_records": total_records,
                "top_model": top_model,
                "recent_models": ["user", "album", "track"],  # TODO: make dynamic later
                "url_prefix": settings.admin_config.admin_prefix_url,
            }
        )
        return context

    async def _add_model_stat(self, model_stats: list, name: str, model: edgy.Model) -> None:
        try:
            count = await model.query.count()
        except Exception:
            count = 0

        model_stats.append(
            {
                "name": name,
                "verbose": model.__name__,
                "count": count,
            }
        )

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

        # For the search
        query = request.query_params.get("q", "").strip()
        page = int(request.query_params.get("page", 1))
        per_page = int(request.query_params.get("per_page", 25))
        per_page = min(max(per_page, 1), 250)

        offset = (page - 1) * per_page

        models = get_registered_models()
        model = models.get(model_name)
        if not model:
            raise NotFound()

        queryset = model.query

        if query:
            filters = []
            for field in model.model_fields.values():
                if field.annotation is str:
                    column = model.table.c.get(field.name)
                    if column is not None:
                        filters.append(column.ilike(f"%{query}%"))

            if filters:
                queryset = queryset.filter(*filters)

        total_records = await queryset.count()
        objects = await queryset.limit(per_page).offset(offset).all()
        total_pages = ceil(total_records / per_page) if total_records else 1

        context.update(
            {
                "title": f"{model.__name__} Details",
                "model": model,
                "objects": objects,
                "model_name": model_name,
                "query": query,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
                "url_prefix": settings.admin_config.admin_prefix_url,
            }
        )
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

    async def get_model_from_foreign_key(self, model_name: str, obj_id: int) -> edgy.Model:
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
        return cast(edgy.Model, instance)

    async def validate_boolean(self, value: str) -> bool:
        return value.lower() in ["true", "1", "yes", "y"]

    async def save_model(
        self, instance: type[edgy.Model], form_data: FormData, create: bool = False
    ) -> edgy.Model:
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
        form_to_dict = {
            k: v
            for k, v in form_data.items()
            if k not in ["pk", "id"] and v is not None and v != ""
        }

        data: dict[str, Any] = {}

        for key, value in form_to_dict.items():
            attribute = instance.meta.fields.get(key)

            if attribute is None:
                continue

            if key in instance.meta.foreign_key_fields:
                # Check if its a ManyToMany field
                if not attribute.is_m2m:
                    data[key] = await instance.meta.fields.get(key).target.query.get(
                        id=self.parse_object_id(value)
                    )
            else:
                if attribute.annotation is bool:
                    data[key] = await self.validate_boolean(value)
                    continue
                data[key] = value

        # Save basic fields first
        if not create:
            await instance.update(**data)
        else:
            instance = await instance.query.create(**data)

        # Handle ManyToMany sync
        for key in instance.meta.many_to_many_fields:
            # What user submitted now
            submitted_ids = {int(v) for v in form_data.getall(key) if v.strip().isdigit()}

            # What was selected before (from hidden input)
            initial_raw = form_data.get(f"_{key}_initial")
            initial_ids = {int(i) for i in initial_raw.split(",")} if initial_raw else set()

            to_add = submitted_ids - initial_ids
            to_remove = initial_ids - submitted_ids
            m2m_field = getattr(instance, key)

            if to_remove:
                model_instances = (
                    await instance.meta.fields.get(key)
                    .target.query.filter(id__in=list(to_remove))
                    .all()
                )
                for model_instance in model_instances:
                    await m2m_field.remove(model_instance)

            if to_add:
                model_instances = (
                    await instance.meta.fields.get(key)
                    .target.query.filter(id__in=list(to_add))
                    .all()
                )
                for model_instance in model_instances:
                    await m2m_field.add(model_instance)

        return cast(edgy.Model, instance)


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
        context = await super().get_context_data(request, **kwargs)  # noqa
        model_name = request.path_params.get("name")
        obj_id = request.path_params.get("id")

        models = get_registered_models()
        model = models.get(model_name)
        if not model:
            raise NotFound()

        instance = await model.query.get_or_none(id=self.get_object_id(request))
        if not instance:
            raise NotFound()

        relationship_fields = {}
        m2m_values = {}

        for field, _ in model.model_fields.items():
            attr = model.meta.fields.get(field)

            if hasattr(attr, "is_m2m") and attr.is_m2m and not isinstance(attr, RelatedField):
                relationship_fields[field] = "many_to_many"
                m2m_values[field] = await getattr(instance, field).all()
            elif (
                hasattr(attr, "is_m2m") and not attr.is_m2m and not isinstance(attr, RelatedField)
            ):
                relationship_fields[field] = "foreign_key"

        context.update(
            {
                "title": f"{model_name.capitalize()} #{obj_id}",
                "object": instance,
                "model": model,
                "model_name": model_name,
                "relationship_fields": relationship_fields,
                "m2m_values": m2m_values,
            }
        )
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
        context = await super().get_context_data(request, **kwargs)  # noqa
        model_name = request.path_params.get("name")
        obj_id = request.path_params.get("id")

        models = get_registered_models()
        model = models.get(model_name)

        if not model:
            raise NotFound()

        instance = await model.query.get(id=self.get_object_id(request))
        if not instance:
            raise NotFound()

        relationship_fields = {}

        for field, _ in model.model_fields.items():
            attr = model.meta.fields.get(field)

            # ManyToMany
            if hasattr(attr, "is_m2m") and attr.is_m2m and not isinstance(attr, RelatedField):
                related_model = attr.target
                all_items = await related_model.query.limit(100).all()
                selected_items = await getattr(instance, field).all()
                selected_ids = [item.id for item in selected_items]
                relationship_fields[field] = {
                    "type": "many_to_many",
                    "items": all_items,
                    "selected": selected_ids,
                }

            # ForeignKey
            elif (
                hasattr(attr, "is_m2m") and not attr.is_m2m and not isinstance(attr, RelatedField)
            ):
                related_model = attr.target
                all_items = await related_model.query.limit(100).all()
                relationship_fields[field] = {
                    "type": "foreign_key",
                    "items": all_items,
                }

        context.update(
            {
                "title": f"Edit {model_name.capitalize()} #{obj_id}",
                "object": instance,
                "model": model,
                "model_name": model_name,
                "relationship_fields": relationship_fields,
            }
        )
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
        return RedirectResponse(
            f"{settings.admin_config.admin_prefix_url}/models/{model_name}/{obj_id}"
        )


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


class ModelCreateView(AdminMixin, BaseObjectView, TemplateController):
    """
    View for displaying and processing the form to create a new model instance.
    """

    template_name = "admin/model_create.html"

    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:
        """
        Prepares the context data for the model creation template.

        Retrieves the model name from the request, finds the corresponding
        model class, and adds it to the context.

        Args:
            request: The incoming Starlette Request object.
            **kwargs: Additional keyword arguments from the path parameters.

        Returns:
            A dictionary containing context data, including the page title,
            the model class, and the model name.

        Raises:
            NotFound: If the model name is not found in the registered models.
        """
        context = await super().get_context_data(request, **kwargs)
        model_name = request.path_params.get("name")

        models = get_registered_models()
        model = models.get(model_name)
        if not model:
            raise NotFound()

        relationship_fields = {}
        for field, field_info in model.model_fields.items():
            if (
                hasattr(field_info, "is_m2m")
                and field_info.is_m2m
                and not isinstance(field_info, RelatedField)
            ):
                related_model = field_info.target
                items = await related_model.query.limit(100).all()
                relationship_fields[field] = {"type": "many_to_many", "items": items}
            elif (
                hasattr(field_info, "is_m2m")
                and not field_info.is_m2m
                and not isinstance(field_info, RelatedField)
            ):
                related_model = field_info.target
                items = await related_model.query.limit(100).all()
                relationship_fields[field] = {"type": "foreign_key", "items": items}

        context.update(
            {
                "title": f"Create {model_name.capitalize()}",
                "model": model,
                "model_name": model_name,
                "relationship_fields": relationship_fields,
            }
        )
        return context

    async def get(self, request: Request, **kwargs: Any) -> Any:
        """
        Handles GET requests to display the model creation form.

        Renders the template configured for this view, populated with
        context data prepared by `get_context_data`.

        Args:
            request: The incoming Starlette Request object.
            **kwargs: Additional keyword arguments from the path parameters.

        Returns:
            The rendered template response containing the creation form.
        """
        return await self.render_template(request, **kwargs)

    async def post(self, request: Request, **kwargs: Any) -> RedirectResponse:
        """
        Handles POST requests to create a new model instance.

        Retrieves the model name and form data from the request, finds the
        corresponding model class, creates a new instance from the form data,
        saves it to the database, and redirects to the detail page of the
        newly created object.

        Args:
            request: The incoming Starlette Request object.
            **kwargs: Additional keyword arguments from the path parameters.

        Returns:
            A RedirectResponse to the detail page of the newly created object.

        Raises:
            NotFound: If the model name is not found in the registered models.
        """
        model_name = request.path_params.get("name")
        form_data = await request.form()

        models = get_registered_models()
        model = models.get(model_name)
        if not model:
            raise NotFound()

        instance = await self.save_model(model, form_data, create=True)
        return RedirectResponse(
            f"{settings.admin_config.admin_prefix_url}/models/{model_name}/{instance.id}"
        )
