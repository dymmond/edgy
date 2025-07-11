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


@lru_cache(maxsize=1)
def get_templates() -> Jinja2Template:
    templates = Jinja2Template(
        directory=[
            *settings.admin_config.admin_extra_templates,
            Path(__file__).resolve().parent / "templates",
        ]
    )
    templates.env.globals["getattr"] = getattr
    templates.env.globals["isinstance"] = isinstance
    return templates


if TYPE_CHECKING:
    from edgy.core.db.models.model import Model


class AdminMixin:
    @property
    def templates(self) -> Jinja2Template:
        return get_templates()

    def get_admin_prefix_url(self, request: Request) -> str:
        if settings.admin_config.admin_prefix_url is not None:
            return settings.admin_config.admin_prefix_url
        return str(request.path_for("admin")).rstrip("/")

    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:  # noqa
        context = {}
        user: Any = None
        with suppress(ImproperlyConfigured):
            user = request.user
        context.update(
            {
                "user": user,
                "isinstance": isinstance,
                "ConcreteFileField": ConcreteFileField,
                "title": settings.admin_config.title,
                "dasboard_title": settings.admin_config.dashboard_title,
                "menu_title": settings.admin_config.menu_title,
                "favicon": settings.admin_config.favicon,
                "sidebar_bg_colour": settings.admin_config.sidebar_bg_colour,
                "url_prefix": self.get_admin_prefix_url(request),
                "messages": get_messages(),
                "create_object_pk": self.create_object_pk,
            }
        )
        return context

    def create_object_pk(self, instance: Model) -> str:
        """
        Extracts the object ID from the request's path parameters.

        Assumes the object ID is present in the path parameters under the key "id".

        Args:
            instance: The model instance

        Returns:
            The object ID as a string.
        """
        pk_dict = {}
        for name in instance.meta.fields["pk"].fieldless_pkcolumns:
            pk_dict[name] = getattr(instance, name)
        for name in instance.pknames:
            pk_dict.update(
                instance.meta.fields[name].clean(name, getattr(instance, name), for_query=True)
            )
        return urlsafe_b64encode(orjson.dumps(pk_dict)).decode()

    def get_object_pk(self, request: Request) -> dict:
        """
        Extracts the object ID from the request's path parameters.

        Assumes the object ID is present in the path parameters under the key "id".

        Args:
            request: The incoming lilya Request object.

        Returns:
            The object ID as dict.
        """
        try:
            result = cast(dict, orjson.loads(urlsafe_b64decode(request.path_params.get("id"))))
            if not isinstance(result, dict):
                raise ObjectNotFound()
            return result
        except orjson.JSONDecodeError:
            raise ObjectNotFound() from None
