from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import anyio
import orjson
from lilya.controllers import Controller
from lilya.exceptions import NotFound  # noqa
from lilya.requests import Request
from lilya.responses import JSONResponse, RedirectResponse
from lilya.templating.controllers import TemplateController
from pydantic import ValidationError

import edgy
from edgy.contrib.admin.mixins import AdminMixin
from edgy.contrib.admin.utils.messages import add_message
from edgy.contrib.pagination import Paginator
from edgy.core.db.fields.file_field import ConcreteFileField
from edgy.core.db.fields.many_to_many import BaseManyToManyForeignKeyField
from edgy.core.db.relationships.related_field import RelatedField
from edgy.exceptions import ObjectNotFound

from .utils.models import (
    add_to_recent_models,
    get_model_json_schema,
    get_recent_models,
    get_registered_models,
)
from .utils.models import get_model as _get_model

if TYPE_CHECKING:
    from edgy.core.db.models.model import Model
    from edgy.core.db.querysets.base import QuerySet


def get_registered_model(model: str) -> type[Model]:
    try:
        return _get_model(model)
    except LookupError:
        raise NotFound() from None


class JSONSchemaView(Controller):
    def get(self, request: Request) -> JSONResponse:
        phase = request.query_params.get("phase", "view")
        with_defaults = request.query_params.get("cdefaults") == "true"
        model_name = request.path_params.get("name")
        reftemplate = "../{model}/json"
        # add phase via f-string
        reftemplate = f"{reftemplate}?phase={phase}"
        if with_defaults:
            reftemplate = f"{reftemplate}&cdefaults=true"
        try:
            schema = get_model_json_schema(
                model_name,
                include_callable_defaults=with_defaults,
                ref_template=reftemplate,
                no_check_admin_models=True,
                phase=phase,
            )
        except LookupError:
            raise NotFound() from None
        # fix defs being plain model/enum names
        if "$defs" in schema:
            new_defs = {}
            for name, model in schema["$defs"].items():
                # is already a matching definition
                if "/" in name:
                    new_defs[name] = model
                else:
                    # let's adapt the plain model/enum name
                    new_defs[reftemplate.format(model=name)] = model
            schema["$defs"] = new_defs
        with JSONResponse.with_transform_kwargs({"json_encode_fn": orjson.dumps}):
            return JSONResponse(schema)


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
                "recent_models": get_recent_models(),
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
                "no_admin_create": model.meta.no_admin_create,
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
        # For the search
        query = request.query_params.get("q", "").strip()
        models = get_registered_models()
        if query:
            lquery = query.lower()
            for mkey in list(models.keys()):
                if lquery not in mkey.lower():
                    models.pop(mkey)
                elif not mkey.lower().startswith(lquery):
                    # reorder back
                    models[mkey] = models.pop(mkey)
            # reorder back not exact start matches
            for mkey in list(models.keys()):
                if not mkey.startswith(query):
                    # reorder back
                    models[mkey] = models.pop(mkey)
        context.update({"title": "Models", "models": models, "query": query})
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
        marshall_class = model.get_admin_marshall_class(phase="list", for_schema=False)
        add_to_recent_models(model)

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
                "marshall_class": marshall_class,
                "page": page_obj,
                "model_name": model_name,
                "query": query,
                "per_page": page_size,
                "total_pages": total_pages,
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

    async def save_model(
        self, instance: edgy.Model | type[edgy.Model], json_data: dict, create: bool = False
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
            json_data: A json dict to update the model.
            create: Is it an update or creation.
        """
        # retrieve fields for extraction, should be broader then get_admin_marshall_for_save
        marshall_class = instance.get_admin_marshall_class(
            phase="create" if create else "update", for_schema=False
        )
        model_fields = marshall_class.model_fields
        data: dict = {}

        for key, value in json_data.items():
            field = model_fields.get(key)

            if field is None or getattr(field, "read_only", False):
                continue
            data[key] = value

        if create:
            marshall = instance.get_admin_marshall_for_save(**data)
        else:
            marshall = instance.get_admin_marshall_for_save(cast("edgy.Model", instance), **data)
        return (await marshall.save()).instance

    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:
        context: dict = await super().get_context_data(request, **kwargs)

        model_name = request.path_params.get("name")

        model = get_registered_model(model_name)
        add_to_recent_models(model)

        context.update(
            {
                "model": model,
                "model_name": model_name,
            }
        )
        return context


class ModelObjectDetailView(BaseObjectView, AdminMixin, TemplateController):
    """
    View for displaying the details of a single object of a specific model.
    """

    template_name = "admin/model_object_detail.html"

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
        model: type[Model] = context["model"]

        instance = await model.query.get_or_none(pk=self.get_object_pk(request))
        if not instance:
            raise NotFound()
        marshall_class = instance.get_admin_marshall_class(phase="view", for_schema=False)
        marshall = marshall_class(instance=instance)
        relationship_fields = {}
        overwrite_values = {}

        for name, field in marshall_class.model_fields.items():
            if isinstance(field, BaseManyToManyForeignKeyField):
                relationship_fields[name] = "many_to_many"
                overwrite_values[name] = await getattr(instance, name).all()
            elif isinstance(field, RelatedField):
                relationship_fields[name] = "related_field"
                overwrite_values[name] = await getattr(instance, name).all()
            elif name in model.meta.foreign_key_fields:
                relationship_fields[name] = "foreign_key"
                overwrite_values[name] = getattr(instance, name)
            elif isinstance(field, ConcreteFileField):
                overwrite_values[name] = getattr(instance, name)

        values = marshall.model_dump(exclude=overwrite_values.keys())
        values.update(overwrite_values)

        context.update(
            {
                "title": f"{model.__name__.capitalize()} #{instance}",
                "marshall_class": marshall_class,
                "values": values,
                "object_pk": self.create_object_pk(instance),
                "relationship_fields": relationship_fields,
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
    template_name = "admin/model_object_edit.html"

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
        model = cast("type[Model]", context["model"])
        instance: Model | None = await cast("QuerySet", model.query).get_or_none(
            pk=self.get_object_pk(request)
        )
        if not instance:
            raise NotFound()
        context["title"] = f"Edit {instance}"
        context["object"] = instance
        marshall = instance.get_admin_marshall_class(phase="view", for_schema=False)(instance)
        json_values = marshall.model_dump_json(exclude_none=True)
        context["values_as_json"] = (
            # replace dangerous chars like in jinja
            json_values.replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026")
            .replace("'", "\\u0027")
        )
        context["object_pk"] = self.create_object_pk(instance)
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

    async def post(self, request: Request, **kwargs: Any) -> RedirectResponse | Any:
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
            instance: Model = await cast("QuerySet", model.query).get(
                pk=self.get_object_pk(request)
            )
        except ObjectNotFound:
            add_message("error", f"Model {model_name} with ID {obj_id} not found.")
            return RedirectResponse(f"{self.get_admin_prefix_url(request)}/models/{model_name}")

        try:
            await self.save_model(instance, orjson.loads((await request.form())["editor_data"]))
        except ValidationError as exc:
            for error in exc.errors():
                for loc in error["loc"]:
                    add_message(
                        "error",
                        f"{loc}: {error['msg']}",
                    )
            return await self.get(request, **kwargs)

        add_message(
            "success",
            f"{instance} has been updated successfully.",
        )
        return RedirectResponse(
            f"{self.get_admin_prefix_url(request)}/models/{model_name}/{obj_id}"
        )


class ModelObjectDeleteView(AdminMixin, Controller):
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
            return RedirectResponse(f"{self.get_admin_prefix_url(request)}/models/{model_name}")
        instance_name = str(instance)
        await instance.delete()

        add_message(
            "success",
            f"{model_name.capitalize()} #{instance_name} has been deleted successfully.",
        )
        return RedirectResponse(f"{self.get_admin_prefix_url(request)}/models/{model_name}")


class ModelObjectCreateView(BaseObjectView, AdminMixin, TemplateController):
    """
    View for displaying and processing the form to create a new model instance.
    """

    template_name = "admin/model_object_create.html"

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
        model_name: str = context["model_name"]

        context.update(
            {
                "title": f"Create {model_name.capitalize()}",
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
        model_name = request.path_params.get("name")

        model = get_registered_model(model_name)
        if (
            model.meta.no_admin_create
            or model.get_admin_marshall_class(
                phase="create", for_schema=False
            ).__incomplete_fields__
        ):
            add_message(
                "error",
                f"For {model.__name__.capitalize()} we cannot create a new instance.",
            )
            return RedirectResponse(
                f"{self.get_admin_prefix_url(request)}/models/{model.__name__}"
            )

        return await self.render_template(request, **kwargs)

    async def post(self, request: Request, **kwargs: Any) -> Any:
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
        if (
            model.meta.no_admin_create
            or model.get_admin_marshall_class(
                phase="create", for_schema=False
            ).__incomplete_fields__
        ):
            add_message(
                "error",
                f"For {model.__name__.capitalize()} we cannot create a new instance.",
            )
            return RedirectResponse(
                f"{self.get_admin_prefix_url(request)}/models/{model.__name__}"
            )

        try:
            instance = await self.save_model(
                model, orjson.loads((await request.form())["editor_data"]), create=True
            )
        except ValidationError as exc:
            for error in exc.errors():
                for loc in error["loc"]:
                    add_message(
                        "error",
                        f"{loc}: {error['msg']}",
                    )
            return await self.get(request, **kwargs)
        obj_id = self.create_object_pk(instance)
        add_message(
            "success",
            f"{model_name.capitalize()} #{instance} has been created successfully.",
        )
        return RedirectResponse(
            f"{self.get_admin_prefix_url(request)}/models/{model_name}/{obj_id}"
        )
