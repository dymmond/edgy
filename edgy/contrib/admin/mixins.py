from typing import Any

from lilya.requests import Request

from edgy.conf import settings


class AdminMixin:
    async def get_context_data(self, request: Request, **kwargs: Any) -> dict:  # noqa
        context = {}
        context.update(
            {
                "title": settings.admin_config.title,
                "menu_title": settings.admin_config.menu_title,
                "favicon": settings.admin_config.favicon,
                "sidebar_bg_colour": settings.admin_config.sidebar_bg_colour,
            }
        )
        return context
