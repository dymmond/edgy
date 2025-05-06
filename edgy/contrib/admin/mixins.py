from pathlib import Path
from typing import Any

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
                "messages": get_messages(request),
            }
        )
        return context
