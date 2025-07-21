from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import anyio
import orjson
from lilya.controllers import Controller
from lilya.exceptions import NotFound
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
    """
    Retrieves a registered Edgy model by its name.

    Args:
        model (str): The name of the model to retrieve.

    Returns:
        type[Model]: The Edgy model class.

    Raises:
        NotFound: If no model with the given name is registered.
    """
    try:
        return _get_model(model)
    except LookupError:
        raise NotFound() from None


class JSONSchemaView(Controller):
    """
    Controller for serving the JSON schema of an Edgy model.

    This view allows clients to retrieve the Pydantic JSON schema
    of any registered Edgy model, useful for form generation or
    API documentation.
    """

    def get(self, request: Request) -> JSONResponse:
        """
        Handles GET requests to retrieve a model's JSON schema.

        Args:
            request (Request): The incoming Lilya request object,
                               expected to contain `name` in path parameters
                               and optional `phase` and `cdefaults` in query parameters.

        Returns:
            JSONResponse: A JSON response containing the model's schema.

        Raises:
            NotFound: If the specified model name is not found.
        """
        # Determine the phase of schema generation (e.g., "view", "edit").
        phase = request.query_params.get("phase", "view")
        # Check if callable defaults should be included in the schema.
        include_callable_defaults = request.query_params.get("cdefaults") == "true"
        # Get the model name from the path parameters.
        model_name = request.path_params.get("name")
        try:
            # Retrieve the JSON schema for the specified model.
            schema = get_model_json_schema(
                model_name,
                include_callable_defaults=include_callable_defaults,
                no_check_admin_models=True,  # Bypass checks for admin-specific models.
                phase=phase,
            )
        except LookupError:
            # If the model is not found, raise a 404 Not Found exception.
            raise NotFound() from None
        # Return the schema as a JSON response, using `orjson.dumps` for serialization.
        with JSONResponse.with_transform_kwargs({"json_encode_fn": orjson.dumps}):
            return JSONResponse(schema)


class AdminDashboard(AdminMixin, TemplateController):
    """
    View for the administration dashboard page.

    This page provides an overview of the registered Edgy models,
    including their record counts and recently accessed models.
    """

    template_name = "admin/dashboard.html"

    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:
        """
        Prepares the context data for the dashboard template.

        Gathers statistics for all registered models, calculates total records,
        identifies the top model by record count, and includes recently
        accessed models.

        Args:
            request (Request): The incoming Lilya Request object.
            **kwargs (Any): Additional keyword arguments.

        Returns:
            dict: A dictionary containing context data for the dashboard.
        """
        context = await super().get_context_data(request, **kwargs)

        models = get_registered_models()
        model_stats: list[dict] = []

        # Use an anyio task group to concurrently fetch model counts for performance.
        async with anyio.create_task_group() as tg:
            for name, model in models.items():
                # Start a new task to add model statistics.
                tg.start_soon(self._add_model_stat, model_stats, name, model)  # type: ignore

        # Calculate total records across all models.
        total_records = sum(m["count"] for m in model_stats)
        # Find the model with the maximum record count.
        top_model = max(
            model_stats, key=lambda m: m["count"], default={"verbose": "N/A", "count": 0}
        )

        context.update(
            {
                "title": "Dashboard",  # Page title.
                "models": sorted(
                    model_stats, key=lambda m: m["verbose"]
                ),  # Sorted list of models with stats.
                "total_records": total_records,  # Total number of records across all models.
                "top_model": top_model,  # The model with the highest record count.
                "recent_models": get_recent_models(),  # List of recently accessed models.
            }
        )
        return context

    async def _add_model_stat(self, model_stats: list, name: str, model: edgy.Model) -> None:
        """
        Fetches the count of records for a given model and appends
        its statistics to the `model_stats` list.

        Args:
            model_stats (list): The list to which model statistics will be appended.
            name (str): The internal name of the model.
            model (edgy.Model): The Edgy model class.
        """
        try:
            # Attempt to get the record count for the model.
            count = await model.query.count()
        except Exception:
            # If an error occurs (e.g., table does not exist), set count to 0.
            count = 0

        model_stats.append(
            {
                "name": name,  # Internal name of the model.
                "verbose": model.__name__,  # Human-readable name of the model.
                "count": count,  # Number of records in the model.
                "no_admin_create": model.meta.no_admin_create,  # Whether model can be created via admin.
            }
        )

    async def get(self, request: Request) -> Any:
        """
        Handles GET requests for the administration dashboard page.

        Args:
            request (Request): The incoming Starlette Request object.

        Returns:
            Any: The rendered template response for the dashboard.
        """
        return await self.render_template(request)


class ModelOverview(AdminMixin, TemplateController):
    """
    View for listing all registered models in the admin interface.

    It provides a searchable overview of all models available for
    administration.
    """

    template_name = "admin/models.html"

    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:
        """
        Prepares the context data for the models list template.

        Retrieves all registered models and filters them based on a search query.

        Args:
            request (Request): The incoming Starlette Request object.
            **kwargs (Any): Additional keyword arguments.

        Returns:
            dict: A dictionary containing context data, including the page title
                  and a list of registered models.
        """
        context = await super().get_context_data(request, **kwargs)
        # Get search query from request parameters.
        query = request.query_params.get("q", "").strip()
        models = get_registered_models()

        if query:
            lquery = query.lower()
            # Filter models based on query, prioritizing exact matches and starts-with.
            for mkey in list(models.keys()):
                if lquery not in mkey.lower():
                    models.pop(mkey)  # Remove models not containing the query.
                elif not mkey.lower().startswith(lquery):
                    # Reorder to prioritize models that start with the query.
                    models[mkey] = models.pop(mkey)
            # Second pass for reordering if not an exact start match.
            for mkey in list(models.keys()):
                if not mkey.startswith(query):
                    models[mkey] = models.pop(mkey)

        context.update({"title": "Models", "models": models, "query": query})
        return context

    async def get(self, request: Request) -> Any:
        """
        Handles GET requests for the registered models list page.

        Args:
            request (Request): The incoming Starlette Request object.

        Returns:
            Any: The rendered template response for the models list.
        """
        return await self.render_template(request)


class ModelDetailView(AdminMixin, TemplateController):
    """
    View for displaying details of a specific model, typically listing its objects.

    This view also includes pagination and search functionality for the objects.
    """

    template_name = "admin/model_detail.html"

    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:
        """
        Prepares the context data for the model detail template.

        Retrieves the model name from the request, finds the corresponding
        model class, applies search filters (if any), paginates the results,
        and adds them to the context.

        Args:
            request (Request): The incoming Starlette Request object.
            **kwargs (Any): Additional keyword arguments from the path parameters.

        Returns:
            dict: A dictionary containing context data, including the model name,
                  the model class, a paginated list of objects, and search parameters.

        Raises:
            NotFound: If the model name is not found in the registered models.
        """
        context = await super().get_context_data(request, **kwargs)
        model_name = request.path_params.get("name")

        # Extract pagination and search parameters from query.
        query = request.query_params.get("q", "").strip()
        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("per_page", 25))
        # Ensure page_size is within a reasonable range.
        page_size = min(max(page_size, 1), 250)

        model = get_registered_model(model_name)
        # Get the marshall class for displaying model data.
        marshall_class = model.get_admin_marshall_class(phase="list", for_schema=False)
        # Add the current model to the list of recently viewed models.
        add_to_recent_models(model)

        queryset = model.query.all()

        if query:
            filters = []
            # Apply text-based search filters to string fields.
            for field in model.model_fields.values():
                if field.annotation is str:
                    column = model.table.c.get(field.name)
                    if column is not None:
                        filters.append(column.ilike(f"%{query}%"))

            if filters:
                # Apply filters to the queryset if any were generated.
                queryset = queryset.filter(*filters)

        # Initialize Paginator with the ordered queryset and page size.
        paginator = Paginator(queryset.order_by(*model.pknames), page_size=page_size)
        # Get the current page of objects.
        page_obj = await paginator.get_page(page)

        # Get the total number of pages.
        total_pages = await paginator.get_amount_pages()

        context.update(
            {
                "title": f"{model.__name__} Details",  # Page title.
                "model": model,  # The model class.
                "marshall_class": marshall_class,  # Marshall class for data display.
                "page": page_obj,  # Paginated objects for the current page.
                "model_name": model_name,  # Name of the model.
                "query": query,  # Current search query.
                "per_page": page_size,  # Number of items per page.
                "total_pages": total_pages,  # Total number of pages.
            }
        )
        return context

    async def get(self, request: Request, **kwargs: Any) -> Any:
        """
        Handles GET requests for the model detail page.

        Renders the template configured for this view, populated with
        context data prepared by `get_context_data`.

        Args:
            request (Request): The incoming Starlette Request object.
            **kwargs (Any): Additional keyword arguments from the path parameters.

        Returns:
            Any: The rendered template response for the model detail page.
        """
        return await self.render_template(request, **kwargs)

    async def post(self, request: Request, **kwargs: Any) -> Any:
        """
        Handles POST requests for the page.

        Currently, this method just re-renders the template. This implies
        that any form submissions or data processing for this view are
        handled elsewhere or not implemented directly within this POST method.

        Args:
            request (Request): The incoming Starlette Request object.
            **kwargs (Any): Additional keyword arguments from the path parameters.

        Returns:
            Any: The rendered template response for the page.
        """
        return await self.render_template(request, **kwargs)


class BaseObjectView:
    """
    Base class for admin views that operate on a single model object.

    Provides utility methods for saving model instances and preparing
    common context data for object-specific views.
    """

    async def save_model(
        self, instance: edgy.Model | type[edgy.Model], json_data: dict, create: bool = False
    ) -> edgy.Model:
        """
        Saves an Edgy model instance based on provided JSON data.

        This method handles mapping `json_data` to model fields, ensuring
        that read-only fields are skipped. It uses the model's marshalling
        capabilities for saving.

        Args:
            instance (edgy.Model | type[edgy.Model]): The Edgy model instance
                                                       to be updated/saved, or
                                                       the model class for creation.
            json_data (dict): A dictionary of data to update the model with.
            create (bool, optional): If `True`, indicates that a new instance
                                     is being created; otherwise, it's an update.
                                     Defaults to `False`.

        Returns:
            edgy.Model: The saved model instance.
        """
        # Retrieve the appropriate marshall class based on the operation phase.
        marshall_class = instance.get_admin_marshall_class(
            phase="create" if create else "update", for_schema=False
        )
        model_fields = marshall_class.model_fields
        data: dict = {}

        # Iterate through the provided JSON data and map to model fields.
        for key, value in json_data.items():
            field = model_fields.get(key)

            # Skip fields that are not in the marshall class or are read-only.
            if field is None or getattr(field, "read_only", False):
                continue
            data[key] = value

        # Create the marshall instance for saving.
        if create:
            marshall = instance.get_admin_marshall_for_save(**data)
        else:
            marshall = instance.get_admin_marshall_for_save(cast("edgy.Model", instance), **data)
        # Save the marshalled instance and return the resulting model.
        return (await marshall.save()).instance

    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:
        """
        Prepares common context data for views operating on a single model object.

        This includes retrieving the model based on the URL parameter and
        adding it to the `recent_models` list.

        Args:
            request (Request): The incoming Lilya Request object.
            **kwargs (Any): Additional keyword arguments from the path parameters.

        Returns:
            dict: A dictionary containing context data, including the model
                  and its name.
        """
        context: dict = await super().get_context_data(request, **kwargs)

        model_name = request.path_params.get("name")

        model = get_registered_model(model_name)
        add_to_recent_models(model)  # Add to recent models list.

        context.update(
            {
                "model": model,  # The Edgy model class.
                "model_name": model_name,  # The name of the model.
            }
        )
        return context


class ModelObjectDetailView(BaseObjectView, AdminMixin, TemplateController):
    """
    View for displaying the details of a single object of a specific model.

    This view shows all fields of an object, including handling of relationships.
    """

    template_name = "admin/model_object_detail.html"

    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:
        """
        Prepares the context data for the model object detail template.

        Retrieves the model instance by its primary key, marshals its data,
        and identifies different types of relationship fields for display.

        Args:
            request (Request): The incoming Starlette Request object.
            **kwargs (Any): Additional keyword arguments from the path parameters.

        Returns:
            dict: A dictionary containing context data, including the model instance,
                  its marshalled values, object primary key, and relationship field types.

        Raises:
            NotFound: If the model instance is not found.
        """
        context = await super().get_context_data(request, **kwargs)  # noqa
        model: type[Model] = context["model"]

        # Retrieve the model instance using its primary key.
        instance = await model.query.get_or_none(pk=self.get_object_pk(request))
        if not instance:
            raise NotFound()  # Raise 404 if instance is not found.

        # Get the marshall class for displaying object details.
        marshall_class = instance.get_admin_marshall_class(phase="view", for_schema=False)
        marshall = marshall_class(instance=instance)
        relationship_fields = {}
        overwrite_values = {}

        # Iterate through marshall class fields to identify relationship types and preload data.
        for name, field in marshall_class.model_fields.items():
            if isinstance(field, BaseManyToManyForeignKeyField):
                relationship_fields[name] = "many_to_many"
                # Load all related objects for ManyToMany fields.
                overwrite_values[name] = await getattr(instance, name).all()
            elif isinstance(field, RelatedField):
                relationship_fields[name] = "related_field"
                # Load all related objects for generic related fields.
                overwrite_values[name] = await getattr(instance, name).all()
            elif name in model.meta.foreign_key_fields:
                relationship_fields[name] = "foreign_key"
                # Get the direct foreign key value.
                overwrite_values[name] = getattr(instance, name)
            elif isinstance(field, ConcreteFileField):
                # Get the file field value.
                overwrite_values[name] = getattr(instance, name)

        # Dump model values, excluding those already handled in `overwrite_values`.
        values = marshall.model_dump(exclude=overwrite_values.keys())
        # Update the values with the preloaded relationship data.
        values.update(overwrite_values)

        context.update(
            {
                "title": f"{model.__name__.capitalize()} #{instance}",  # Page title.
                "marshall_class": marshall_class,  # Marshall class used.
                "values": values,  # Displayable values of the object.
                "object_pk": self.create_object_pk(instance),  # URL-safe PK string.
                "relationship_fields": relationship_fields,  # Mapping of field names to relationship types.
            }
        )
        return context

    async def get(self, request: Request, **kwargs: Any) -> Any:
        """
        Handles GET requests for the model object detail page.

        Renders the template configured for this view, populated with
        context data prepared by `get_context_data`.

        Args:
            request (Request): The incoming Starlette Request object.
            **kwargs (Any): Additional keyword arguments from the path parameters.

        Returns:
            Any: The rendered template response for the object detail page.
        """
        return await self.render_template(request, **kwargs)

    async def post(self, request: Request, **kwargs: Any) -> Any:
        """
        Handles POST requests for the model object detail page.

        Currently, this method simply re-renders the template, as editing
        logic is handled by `ModelObjectEditView`.

        Args:
            request (Request): The incoming Starlette Request object.
            **kwargs (Any): Additional keyword arguments from the path parameters.

        Returns:
            Any: The rendered template response for the object detail page.
        """
        return await self.render_template(request, **kwargs)


class ModelObjectEditView(BaseObjectView, AdminMixin, TemplateController):
    """
    View for displaying and processing the form to edit an existing model instance.
    """

    template_name = "admin/model_object_edit.html"

    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:
        """
        Prepares the context data for the model edit template.

        Retrieves the model instance to be edited, generates its JSON schema
        for form rendering, and prepares existing values for pre-populating
        the form.

        Args:
            request (Request): The incoming Starlette Request object.
            **kwargs (Any): Additional keyword arguments from the path parameters.

        Returns:
            dict: A dictionary containing context data for the template, including
                  the page title, the model instance, its JSON schema, and initial values.

        Raises:
            NotFound: If the model name or the specific instance is not found.
        """
        context = await super().get_context_data(request, **kwargs)  # noqa
        model = cast("type[Model]", context["model"])
        # Retrieve the instance to be edited.
        instance: Model | None = await cast("QuerySet", model.query).get_or_none(
            pk=self.get_object_pk(request)
        )
        if not instance:
            raise NotFound()  # Raise 404 if instance is not found.

        context["title"] = f"Edit {instance}"  # Page title.
        context["object"] = instance  # The model instance being edited.
        # Generate the JSON schema for the edit form.
        context["schema"] = self.get_schema(model, phase="edit", include_callable_defaults=True)

        # Marshal the instance data for display in the form.
        marshall = instance.get_admin_marshall_class(phase="edit", for_schema=False)(instance)
        json_values = marshall.model_dump_json(exclude_none=True)
        # Sanitize JSON values for safe embedding in HTML.
        context["values_as_json"] = (
            json_values.replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026")
            .replace("'", "\\u0027")
        )
        context["object_pk"] = self.create_object_pk(instance)  # URL-safe PK string.
        return context

    async def get(self, request: Request, **kwargs: Any) -> Any:
        """
        Handles GET requests to display the model edit form.

        Renders the template configured for this view, populated with
        context data prepared by `get_context_data`.

        Args:
            request (Request): The incoming Starlette Request object.
            **kwargs (Any): Additional keyword arguments from the path parameters.

        Returns:
            Any: The rendered template response containing the edit form.
        """
        return await self.render_template(request, **kwargs)

    async def post(self, request: Request, **kwargs: Any) -> RedirectResponse | Any:
        """
        Handles POST requests to save the changes to a model instance.

        Retrieves form data, attempts to update the model instance, and
        redirects on success. On validation errors, it adds messages and
        re-renders the form with errors.

        Args:
            request (Request): The incoming Starlette Request object.
            **kwargs (Any): Additional keyword arguments from the path parameters.

        Returns:
            RedirectResponse | Any: A redirect response on success, or the
                                    rendered template with errors on failure.

        Raises:
            NotFound: If the model or the specific instance is not found.
        """
        model_name = request.path_params.get("name")
        obj_id = request.path_params.get("id")

        model = get_registered_model(model_name)

        try:
            # Retrieve the instance to be updated.
            instance: Model = await cast("QuerySet", model.query).get(
                pk=self.get_object_pk(request)
            )
        except ObjectNotFound:
            # If instance not found, add an error message and redirect.
            add_message("error", f"Model {model_name} with ID {obj_id} not found.")
            return RedirectResponse(f"{self.get_admin_prefix_url(request)}/models/{model_name}")

        try:
            # Parse the JSON data from the form and save the model.
            editor_data_form_field = await request.form()
            await self.save_model(instance, orjson.loads(editor_data_form_field["editor_data"]))
        except ValidationError as exc:
            # If validation fails, add error messages for each validation error.
            for error in exc.errors():
                for loc in error["loc"]:
                    add_message(
                        "error",
                        f"{loc}: {error['msg']}",
                    )
            # Re-render the form with error messages.
            return await self.get(request, **kwargs)

        # On successful update, add a success message and redirect to the detail page.
        add_message(
            "success",
            f"{instance} has been updated successfully.",
        )
        return RedirectResponse(
            f"{self.get_admin_prefix_url(request)}/models/{model_name}/{obj_id}"
        )


class ModelObjectDeleteView(AdminMixin, Controller):
    """
    Controller for handling the deletion of a specific model instance.
    """

    async def post(self, request: Request, **kwargs: Any) -> RedirectResponse:
        """
        Handles POST requests to delete a model instance.

        Retrieves the model and instance, performs the deletion, and
        redirects the user to the model's listing page with a confirmation message.

        Args:
            request (Request): The incoming Starlette Request object.
            **kwargs (Any): Additional keyword arguments from the path parameters.

        Returns:
            RedirectResponse: A redirect response to the model's listing page.

        Raises:
            NotFound: If the model or the specific instance to be deleted is not found.
        """
        model_name = request.path_params.get("name")
        obj_id = request.path_params.get("id")

        model = get_registered_model(model_name)

        try:
            # Retrieve the instance to be deleted.
            instance = await model.query.get(pk=self.get_object_pk(request))
        except ObjectNotFound:
            # If instance not found, add an error message and redirect.
            add_message("error", f"There is no record with this ID: '{obj_id}'.")
            return RedirectResponse(f"{self.get_admin_prefix_url(request)}/models/{model_name}")

        instance_name = str(instance)  # Store instance name before deletion for the message.
        await instance.delete()  # Perform the deletion.

        # On successful deletion, add a success message and redirect.
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

        Retrieves the model class and generates its JSON schema for the
        creation form.

        Args:
            request (Request): The incoming Starlette Request object.
            **kwargs (Any): Additional keyword arguments from the path parameters.

        Returns:
            dict: A dictionary containing context data, including the page title,
                  the model class, and its JSON schema for creation.

        Raises:
            NotFound: If the model name is not found in the registered models.
        """
        context = await super().get_context_data(request, **kwargs)
        model_name: str = context["model_name"]
        # Generate the JSON schema for the creation form.
        context["schema"] = self.get_schema(
            context["model"], phase="create", include_callable_defaults=True
        )
        context["title"] = f"Create {model_name.capitalize()}"  # Page title.
        return context

    async def get(self, request: Request, **kwargs: Any) -> Any:
        """
        Handles GET requests to display the model creation form.

        Checks if the model allows creation via the admin interface and if
        all necessary fields for creation are complete. If not, it redirects
        with an error message. Otherwise, it renders the creation form.

        Args:
            request (Request): The incoming Starlette Request object.
            **kwargs (Any): Additional keyword arguments from the path parameters.

        Returns:
            Any: The rendered template response containing the creation form,
                 or a RedirectResponse if creation is not allowed.
        """
        model_name = request.path_params.get("name")

        model = get_registered_model(model_name)
        # Check if model creation is disallowed or if marshalling fields are incomplete.
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
            # Redirect to the model's overview page if creation is not allowed.
            return RedirectResponse(
                f"{self.get_admin_prefix_url(request)}/models/{model.__name__}"
            )

        return await self.render_template(request, **kwargs)

    async def post(self, request: Request, **kwargs: Any) -> Any:
        """
        Handles POST requests to create a new model instance.

        Retrieves form data, attempts to create and save a new model instance.
        On success, it redirects to the detail page of the new object.
        On validation errors, it adds messages and re-renders the creation form.

        Args:
            request (Request): The incoming Starlette Request object.
            **kwargs (Any): Additional keyword arguments from the path parameters.

        Returns:
            Any: A redirect response on successful creation, or the rendered
                 template with errors on failure.

        Raises:
            NotFound: If the model name is not found in the registered models.
        """
        model_name = request.path_params.get("name")

        model = get_registered_model(model_name)
        # Perform the same checks as in GET to ensure creation is allowed.
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
            # Parse the JSON data from the form and save the new model instance.
            editor_data_form_field = await request.form()
            instance = await self.save_model(
                model, orjson.loads(editor_data_form_field["editor_data"]), create=True
            )
        except ValidationError as exc:
            # If validation fails, add error messages for each validation error.
            for error in exc.errors():
                for loc in error["loc"]:
                    add_message(
                        "error",
                        f"{loc}: {error['msg']}",
                    )
            # Re-render the form with error messages.
            return await self.get(request, **kwargs)

        # On successful creation, generate the object's primary key string.
        obj_id = self.create_object_pk(instance)
        # Add a success message.
        add_message(
            "success",
            f"{model_name.capitalize()} #{instance} has been created successfully.",
        )
        # Redirect to the detail page of the newly created object.
        return RedirectResponse(
            f"{self.get_admin_prefix_url(request)}/models/{model_name}/{obj_id}"
        )
