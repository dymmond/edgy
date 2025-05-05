from typing import Any

from lilya.requests import Request
from lilya.templating.controllers import TemplateController

from edgy.contrib.admin.mixins import AdminMixin


class AdminDashboard(AdminMixin, TemplateController):
    template_name = "admin/base.html"

    async def get(self, request: Request) -> Any:
        return await self.render_template(request)
