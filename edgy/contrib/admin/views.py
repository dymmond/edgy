from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Union, cast, get_args, get_origin

import anyio
import orjson
from lilya.controllers import Controller
from lilya.exceptions import NotFound  # noqa
from lilya.requests import Request
from lilya.responses import JSONResponse, RedirectResponse
from lilya.templating.controllers import TemplateController

import edgy
from edgy.conf import settings
from edgy.contrib.admin.mixins import AdminMixin
from edgy.contrib.admin.utils.messages import add_message
from edgy.contrib.pagination import Paginator
from edgy.core.db.relationships.related_field import RelatedField
from edgy.exceptions import ObjectNotFound

from .utils.models import get_model as _get_model
from .utils.models import get_model_json_schema, get_registered_models

if TYPE_CHECKING:
    from edgy.core.db.models.model import Model


def get_registered_model(model: str) -> type[Model]:
    try:
        return _get_model(model)
    except LookupError:
        raise NotFound() from None


def get_input_type(annotation: Any) -> str:
    """
    Unwraps Optional/Union[..., None] to find the real type,
    then returns one of: 'bool', 'date', 'datetime', or 'text'.
    """
    origin = get_origin(annotation)
    if origin is Union:
        # strip out NoneType
        args = [a for a in get_args(annotation) if a is not type(None)]
        if len(args) == 1:
            annotation = args[0]

    if annotation is bool:
        return "bool"
    if annotation is date:
        return "date"
    if annotation is datetime:
        return "datetime"
    return "text"


class JSONSchemaView(Controller):
    def get(self, request: Request) -> JSONResponse:
        with_defaults = request.query_params.get("cdefaults") == "true"
        model_name = request.path_params.get("name")
        try:
            with JSONResponse.with_transform_kwargs({"json_encode_fn": orjson.dumps}):
                return JSONResponse(
                    get_model_json_schema(
                        model_name,
                        include_callable_defaults=with_defaults,
                        ref_template="../{model}/json",
                    )
                )
        except LookupError:
            raise NotFound() from None


class AdminDashboard(AdminMixin, TemplateController):
    """
    View for the administration dashboard page.
    """

    template_name = "admin/dashboard.html"

    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:
        """
        Prepares the context data for the dashboard template.

        Args:
            request: The incoming Lilya Request object.
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


class ModelOverview(AdminMixin, TemplateController):
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
        page_size = int(request.query_params.get("per_page", 25))
        page_size = min(max(page_size, 1), 250)

        model = get_registered_model(model_name)

        queryset = model.query.all()

        if query:
            filters = []
            for field in model.model_fields.values():
                if field.annotation is str:
                    column = model.table.c.get(field.name)
                    if column is not None:
                        filters.append(column.ilike(f"%{query}%"))

            if filters:
                queryset = queryset.filter(*filters)
        paginator = Paginator(queryset.order_by(*model.pknames), page_size=page_size)
        page_obj = await paginator.get_page(page)

        total_pages = await paginator.get_amount_pages()

        context.update(
            {
                "title": f"{model.__name__} Details",
                "model": model,
                "page": page_obj,
                "model_name": model_name,
                "query": query,
                "per_page": page_size,
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

    def get_object_pk(self, request: Request) -> dict:
        """
        Extracts the object ID from the request's path parameters.

        Assumes the object ID is present in the path parameters under the key "id".

        Args:
            request: The incoming Starlette Request object.

        Returns:
            The object ID as dict.
        """
        return cast(dict, orjson.loads(urlsafe_b64decode(request.path_params.get("id"))))

    def create_object_pk(self, pk: dict) -> str:
        """
        Extracts the object ID from the request's path parameters.

        Assumes the object ID is present in the path parameters under the key "id".

        Args:
            request: The incoming Starlette Request object.

        Returns:
            The object ID as a string.
        """
        return urlsafe_b64encode(orjson.dumps(pk)).decode()

    async def validate_boolean(self, value: str) -> bool:
        return value.lower() in ["true", "1", "yes", "y"]

    async def save_model(
        self, instance: type[edgy.Model], json_data: dict, create: bool = False
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
        data: dict[str, Any] = {}

        for key, value in json_data.items():
            field = instance.meta.fields.get(key)

            if field is None or field.read_only:
                continue

            if key in instance.meta.foreign_key_fields:
                # Check if its a ManyToMany m2m field
                if not field.is_m2m:
                    target = instance.meta.fields.get(key).target
                    data[key] = await target.query.first(pk=self.get_object_pk(value))
                    if data[key] is None:
                        data[key] = target(**value)
            elif key in instance.meta.many_to_many_fields:
                continue
            else:
                data[key] = value

        # Save basic fields first
        if not create:
            await instance.update(**data)
        else:
            instance = await instance.query.create(**data)

        # Handle ManyToMany sync
        for key in instance.meta.many_to_many_fields:
            m2m_data = json_data.get(key, [])
            if m2m_data:
                rel = getattr(instance, key)
                for dataob in m2m_data:
                    await rel.add(dataob)

        return cast(edgy.Model, instance)


class ModelObjectDetailView(BaseObjectView, AdminMixin, TemplateController):
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

        model = get_registered_model(model_name)

        instance = await model.query.get_or_none(pk=self.get_object_pk(request))
        if not instance:
            raise NotFound()

        relationship_fields = {}
        m2m_values = {
            await getattr(instance, name).all() for name in model.meta.many_to_many_fields
        }

        for field in model.meta.relationship_fields:
            if field in m2m_values:
                relationship_fields[field] = "many_to_many"
            elif field in model.meta.foreign_key_fields:
                relationship_fields[field] = "foreign_key"

        context.update(
            {
                "title": f"{model_name.capitalize()} #{instance}",
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


class ModelObjectEditView(BaseObjectView, AdminMixin, TemplateController):
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

        model = get_registered_model(model_name)

        instance = await model.query.get_or_none(pk=self.get_object_pk(request))
        if not instance:
            raise NotFound()

        relationship_fields = {}

        for field in model.meta.relationship_fields:
            attr = model.meta.fields.get(field)
            if isinstance(attr, RelatedField):
                continue

            # ManyToMany
            if hasattr(attr, "is_m2m") and attr.is_m2m:
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
            elif hasattr(attr, "is_m2m") and not attr.is_m2m:
                related_model = attr.target
                all_items = await related_model.query.limit(100).all()
                relationship_fields[field] = {
                    "type": "foreign_key",
                    "items": all_items,
                }

        context.update(
            {
                "title": f"Edit {instance}",
                "object": instance,
                "model": model,
                "model_name": model_name,
                "relationship_fields": relationship_fields,
                "get_input_type": get_input_type,
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

        model = get_registered_model(model_name)

        try:
            instance = await model.query.get(pk=self.get_object_pk(request))
        except ObjectNotFound:
            add_message("error", f"Model {model_name} with ID {obj_id} not found.")
            return RedirectResponse(
                f"{settings.admin_config.admin_prefix_url}/models/{model_name}"
            )

        await self.save_model(instance, orjson.loads(await request.data()))

        add_message(
            "success",
            f"{instance} has been updated successfully.",
        )
        return RedirectResponse(
            f"{settings.admin_config.admin_prefix_url}/models/{model_name}/{obj_id}"
        )


class ModelObjectDeleteView(BaseObjectView, AdminMixin, TemplateController):
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
        obj_id = request.path_params.get("id")

        model = get_registered_model(model_name)

        try:
            instance = await model.query.get(pk=self.get_object_pk(request))
        except ObjectNotFound:
            add_message("error", f"There is no record with this ID: '{obj_id}'.")
            return RedirectResponse(
                f"{settings.admin_config.admin_prefix_url}/models/{model_name}"
            )

        await instance.delete()

        add_message(
            "success",
            f"{model_name.capitalize()} #{obj_id} has been deleted successfully.",
        )
        return RedirectResponse(f"{settings.admin_config.admin_prefix_url}/models/{model_name}")


class ModelObjectCreateView(BaseObjectView, AdminMixin, TemplateController):
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

        model = get_registered_model(model_name)

        relationship_fields = {}
        for field in model.meta.relationship_fields:
            field_info = model.meta.fields.get(field)
            if isinstance(field_info, RelatedField):
                continue

            if hasattr(field_info, "is_m2m") and field_info.is_m2m:
                related_model = field_info.target
                items = await related_model.query.limit(100).all()
                relationship_fields[field] = {"type": "many_to_many", "items": items}
            elif hasattr(field_info, "is_m2m") and not field_info.is_m2m:
                related_model = field_info.target
                items = await related_model.query.limit(100).all()
                relationship_fields[field] = {"type": "foreign_key", "items": items}

        context.update(
            {
                "title": f"Create {model_name.capitalize()}",
                "model": model,
                "model_name": model_name,
                "relationship_fields": relationship_fields,
                "get_input_type": get_input_type,
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

        model = get_registered_model(model_name)

        instance = await self.save_model(model, orjson.loads(await request.data()), create=True)
        add_message(
            "success",
            f"{model_name.capitalize()} #{instance.id} has been created successfully.",
        )
        return RedirectResponse(
            f"{settings.admin_config.admin_prefix_url}/models/{model_name}/{instance.id}"
        )
