from typing import Any, Coroutine

from esmerald import Request
from esmerald.protocols.middleware import MiddlewareProtocol
from myapp.models import Tenant, TenantUser, User
from starlette.types import ASGIApp, Receive, Scope, Send

from edgy import ObjectNotFound
from edgy.core.db import set_tenant


class TenantMiddleware(MiddlewareProtocol):
    def __init__(self, app: "ASGIApp"):
        super().__init__(app)
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> Coroutine[Any, Any, None]:
        """
        The middleware reads the `tenant` and `email` from the headers
        and uses it to run the queries against the database records.

        If there is a relationship between `User` and `Tenant` in the
        `TenantUser`, it will use the `set_tenant` to set the global
        tenant for the user calling the APIs.
        """
        request = Request(scope=scope, receive=receive, send=send)

        schema = request.headers.get("tenant", None)
        email = request.headers.get("email", None)

        try:
            tenant = await Tenant.query.get(schema_name=schema)
            user = await User.query.get(email=email)

            # Raises ObjectNotFound if there is no relation.
            await TenantUser.query.get(tenant=tenant, user=user)
            tenant = tenant.schema_name
        except ObjectNotFound:
            tenant = None

        set_tenant(tenant)
        await self.app(scope, receive, send)
