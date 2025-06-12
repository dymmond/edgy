import base64
import secrets

from lilya.exceptions import PermissionDenied
from lilya.protocols.permissions import PermissionProtocol
from lilya.requests import Request
from lilya.types import ASGIApp, Receive, Scope, Send


class BasicAuthAccess(PermissionProtocol):
    def __init__(
        self, app: ASGIApp, *, username: str = "admin", password: str, print_pw: bool = False
    ) -> None:
        self.app = app
        self.basic_string = base64.b64encode(f"{username}:{password}".encode()).decode()
        if print_pw:
            print("The admin panel password is:", password)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope=scope, receive=receive, send=send)
        if "Authorization" not in request.headers:
            raise PermissionDenied(
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Admin panel", charset="UTF-8"'},
            )

        auth = request.headers["Authorization"]
        try:
            scheme, credentials = auth.split()
            if scheme.lower() != "basic":
                raise PermissionDenied(
                    status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="Admin panel", charset="UTF-8"'},
                )
        except ValueError as exc:
            raise PermissionDenied(
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Admin panel", charset="UTF-8"'},
            ) from exc

        if not secrets.compare_digest(credentials, self.basic_string):
            raise PermissionDenied(
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Admin panel", charset="UTF-8"'},
            )

        await self.app(scope, receive, send)
