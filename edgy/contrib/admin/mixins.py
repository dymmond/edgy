from base64 import urlsafe_b64encode
from pathlib import Path
from typing import Any

import orjson
from lilya.requests import Request
from lilya.templating import Jinja2Template

from edgy.conf import settings
from edgy.contrib.admin.utils.messages import get_messages

templates = Jinja2Template(directory=str(Path(__file__).resolve().parent / "templates"))
templates.env.globals["getattr"] = getattr


class AdminMixin:
    templates = templates

    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:  # noqa
        context = {}
        context.update(
            {
                "title": settings.admin_config.title,
                "dasboard_title": settings.admin_config.dashboard_title,
                "menu_title": settings.admin_config.menu_title,
                "favicon": settings.admin_config.favicon,
                "sidebar_bg_colour": settings.admin_config.sidebar_bg_colour,
                "url_prefix": settings.admin_config.admin_prefix_url,
                "messages": get_messages(),
                "create_object_pk": self.create_object_pk,
            }
        )
        return context

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
