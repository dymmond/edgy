from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from contextlib import suppress
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import orjson
from lilya.exceptions import ImproperlyConfigured
from lilya.requests import Request
from lilya.templating import Jinja2Template

from edgy.conf import settings
from edgy.contrib.admin.utils.messages import get_messages
from edgy.core.db.fields.file_field import ConcreteFileField
from edgy.exceptions import ObjectNotFound

from .utils.models import get_model_json_schema


@lru_cache(maxsize=1)
def get_templates() -> Jinja2Template:
    """
    Retrieves and caches the Jinja2Template instance for the admin interface.

    This function ensures that the template environment is initialized only once,
    incorporating any extra template directories defined in settings and
    adding global functions like `getattr` and `isinstance` for use within templates.

    Returns:
        Jinja2Template: The configured Jinja2Template instance.
    """
    templates = Jinja2Template(
        directory=[
            # Include extra template directories specified in admin settings.
            *settings.admin_config.admin_extra_templates,
            # Include the default templates directory relative to this file.
            Path(__file__).resolve().parent / "templates",
        ]
    )
    # Add 'getattr' and 'isinstance' as global functions available directly in Jinja2 templates.
    templates.env.globals["getattr"] = getattr
    templates.env.globals["isinstance"] = isinstance
    return templates


if TYPE_CHECKING:
    from edgy.core.db.models.model import Model


class AdminMixin:
    """
    A mixin class providing common utilities and properties for Edgy Admin views.

    This includes access to the Jinja2 template environment, methods for
    determining the admin URL prefix, preparing context data for templates,
    and handling primary key encoding/decoding for URLs.
    """

    @property
    def templates(self) -> Jinja2Template:
        """
        Provides access to the configured Jinja2Template instance.

        Returns:
            Jinja2Template: The Jinja2Template instance.
        """
        return get_templates()

    def get_admin_prefix_url(self, request: Request) -> str:
        """
        Determines the base URL prefix for the Edgy Admin interface.

        It first checks `settings.admin_config.admin_prefix_url`. If not set,
        it derives the prefix from the `admin` route's path.

        Args:
            request (Request): The incoming Lilya request object.

        Returns:
            str: The URL prefix for the admin interface, without a trailing slash.
        """
        if settings.admin_config.admin_prefix_url is not None:
            return settings.admin_config.admin_prefix_url
        # If no explicit prefix is set, use the path of the 'admin' route.
        # .rstrip('/') removes any trailing slash to ensure consistency.
        return str(request.path_for("admin")).rstrip("/")

    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:  # noqa
        """
        Prepares and returns a dictionary of context data for rendering admin templates.

        This context includes common information like user details, admin configuration
        settings, messages, and utility functions.

        Args:
            request (Request): The incoming Lilya request object.
            **kwargs (Any): Additional keyword arguments to include in the context.

        Returns:
            dict: A dictionary containing context variables for templates.
        """
        context = {}
        user: Any = None
        # Attempt to retrieve the current user from the request, suppressing
        # ImproperlyConfigured if user middleware is not set up.
        with suppress(ImproperlyConfigured):
            user = request.user
        context.update(
            {
                "user": user,  # The currently authenticated user.
                "isinstance": isinstance,  # Python's isinstance function.
                "ConcreteFileField": ConcreteFileField,  # Reference to ConcreteFileField.
                "title": settings.admin_config.title,  # Main title of the admin.
                "dasboard_title": settings.admin_config.dashboard_title,  # Dashboard specific title.
                "menu_title": settings.admin_config.menu_title,  # Menu title.
                "favicon": settings.admin_config.favicon,  # Favicon URL.
                "sidebar_bg_colour": settings.admin_config.sidebar_bg_colour,  # Sidebar background color.
                "url_prefix": self.get_admin_prefix_url(request),  # Admin URL prefix.
                "messages": get_messages(),  # Flash messages from the session.
                "create_object_pk": self.create_object_pk,  # Function to create object PK.
            }
        )
        return context

    def create_object_pk(self, instance: Model) -> str:
        """
        Generates a URL-safe, base64-encoded string representing the primary key
        (or composite primary keys) of a given model instance.

        This is used to safely pass primary key information in URLs, especially
        for models with composite primary keys.

        Args:
            instance (Model): The model instance for which to create the primary key string.

        Returns:
            str: The URL-safe, base64-encoded primary key string.
        """
        pk_dict = {}
        # Collect values for fieldless primary key columns.
        for name in instance.meta.fields["pk"].fieldless_pkcolumns:
            pk_dict[name] = getattr(instance, name)
        # Collect and clean values for named primary key columns.
        for name in instance.pknames:
            pk_dict.update(
                instance.meta.fields[name].clean(name, getattr(instance, name), for_query=True)
            )
        # Serialize the dictionary to JSON and then base64 encode it to be URL-safe.
        return urlsafe_b64encode(orjson.dumps(pk_dict)).decode()

    def get_object_pk(self, request: Request) -> dict:
        """
        Extracts and decodes the object's primary key from the request's path parameters.

        It expects the primary key to be present in the path parameters under the key "id"
        as a URL-safe base64 encoded JSON string.

        Args:
            request (Request): The incoming Lilya Request object.

        Raises:
            ObjectNotFound: If the "id" parameter is missing, invalid, or cannot be decoded.

        Returns:
            dict: A dictionary representation of the object's primary key.
        """
        try:
            # Retrieve the 'id' from path parameters and base64 decode it.
            # Then, parse the JSON string into a dictionary.
            result = cast(
                dict, orjson.loads(urlsafe_b64decode(cast(str, request.path_params.get("id"))))
            )
            # Ensure the decoded result is actually a dictionary.
            if not isinstance(result, dict):
                raise ObjectNotFound()
            return result
        except orjson.JSONDecodeError:
            # Catch JSON decoding errors and re-raise as ObjectNotFound.
            raise ObjectNotFound() from None

    def get_schema(
        self, model: type[Model] | str, *, include_callable_defaults: bool, phase: str
    ) -> str:
        """
        Generates and returns the JSON schema for a given model.

        This schema is sanitized to replace potentially dangerous HTML characters,
        making it safe for embedding directly into HTML templates.

        Args:
            model (type[Model] | str): The model class or its name for which
                                       to generate the JSON schema.
            include_callable_defaults (bool): If `True`, includes callable
                                              default values in the schema.
            phase (str): The current phase of schema generation (e.g., "build", "run").

        Returns:
            str: The JSON schema as a string, with dangerous characters replaced.
        """
        # Generate the JSON schema using Edgy's utility function.
        schema = orjson.dumps(
            get_model_json_schema(
                model,
                include_callable_defaults=include_callable_defaults,
                no_check_admin_models=True,  # Bypass checks specific to admin models.
                phase=phase,
            )
        ).decode()
        # Replace dangerous HTML characters with their Unicode escape sequences
        # to prevent XSS vulnerabilities when embedding in HTML.
        return (
            schema.replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026")
            .replace("'", "\\u0027")
        )
