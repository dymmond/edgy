from lilya.exceptions import PermissionDenied
from lilya.protocols.permissions import PermissionProtocol
from lilya.requests import Request
from lilya.types import ASGIApp, Receive, Scope, Send


class AuthorizedAccess(PermissionProtocol):
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope=scope, receive=receive, send=send)
        user = request.user

        if user is not None and user.is_authenticated:
            await self.app(scope, receive, send)
            return
        raise PermissionDenied()


class AdminAccess(PermissionProtocol):
    def __init__(self, app: ASGIApp, admin_attribute: str = "is_admin") -> None:
        self.app = app
        self.admin_attribute = admin_attribute

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope=scope, receive=receive, send=send)
        user = request.user

        if (
            user is not None
            and user.is_authenticated
            and getattr(user, self.admin_attribute, False)
        ):
            await self.app(scope, receive, send)
            return
        raise PermissionDenied()
