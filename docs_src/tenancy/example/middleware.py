from typing import Any, Coroutine

from ravyn import Request
from ravyn.core.protocols.middleware import MiddlewareProtocol
from lilya.types import ASGIApp, Receive, Scope, Send

from edgy.core.db import with_tenant
from edgy.exceptions import ObjectNotFound


class TenantMiddleware(MiddlewareProtocol):
    def __init__(self, app: "ASGIApp"):
        super().__init__(app)
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> Coroutine[Any, Any, None]:
        """
        Receives a header with the tenant information and lookup in
        the database if exists.

        Sets the tenant if true, or none otherwise.
        """
        request = Request(scope=scope, receive=receive, send=send)
        tenant_header = request.headers.get("tenant", None)

        try:
            user = await Tenant.query.get(schema_name=tenant_header)
            tenant = user.schema_name
        except ObjectNotFound:
            tenant = None

        with with_tenant(tenant):
            await self.app(scope, receive, send)
