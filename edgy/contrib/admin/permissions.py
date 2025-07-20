from __future__ import annotations

import base64
import secrets

from lilya.exceptions import PermissionDenied
from lilya.protocols.permissions import PermissionProtocol
from lilya.requests import Request
from lilya.types import ASGIApp, Receive, Scope, Send


class BasicAuthAccess(PermissionProtocol):
    """
    A Lilya permission protocol that implements HTTP Basic Authentication.

    This class acts as an ASGI middleware to protect routes by requiring
    a username and password. It checks the 'Authorization' header for
    Basic authentication credentials and denies access if they are missing
    or incorrect.
    """

    def __init__(
        self, app: ASGIApp, *, username: str = "admin", password: str, print_pw: bool = False
    ) -> None:
        """
        Initializes the BasicAuthAccess permission.

        Args:
            app (ASGIApp): The ASGI application to wrap.
            username (str, optional): The expected username for authentication.
                                      Defaults to "admin".
            password (str): The expected password for authentication.
            print_pw (bool, optional): If `True`, the password will be printed
                                       to the console during initialization.
                                       **Use with extreme caution and only for
                                       development purposes.** Defaults to `False`.
        """
        self.app = app
        # Encode the username and password into a base64 string as required for Basic Auth.
        self.basic_string = base64.b64encode(f"{username}:{password}".encode()).decode()
        # Optionally print the password for debugging purposes.
        if print_pw:
            print("The admin panel password is:", password)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        The ASGI callable method that implements the permission check.

        This method intercepts the request, checks for the 'Authorization' header,
        validates the Basic authentication credentials, and either allows the
        request to proceed to the wrapped application or raises a `PermissionDenied`
        exception.

        Args:
            scope (Scope): The ASGI scope dictionary.
            receive (Receive): The ASGI receive callable.
            send (Send): The ASGI send callable.

        Raises:
            PermissionDenied: If authentication fails, with appropriate
                              WWW-Authenticate headers for the browser.
        """
        # Create a Request object from the ASGI scope, receive, and send callables.
        request = Request(scope=scope, receive=receive, send=send)

        # Check if the 'Authorization' header is present in the request.
        if "Authorization" not in request.headers:
            # If not present, raise PermissionDenied with a 401 status and
            # WWW-Authenticate header to prompt for credentials.
            raise PermissionDenied(
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Admin panel", charset="UTF-8"'},
            )

        # Retrieve the value of the 'Authorization' header.
        auth = request.headers["Authorization"]
        try:
            # Split the header value into scheme (e.g., "Basic") and credentials.
            scheme, credentials = auth.split()
            # Check if the scheme is "basic" (case-insensitive).
            if scheme.lower() != "basic":
                # If not basic, raise PermissionDenied.
                raise PermissionDenied(
                    status_code=401,
                    headers={"WWW-Authenticate": 'Basic realm="Admin panel", charset="UTF-8"'},
                )
        except ValueError as exc:
            # Catch ValueError if split() fails (e.g., malformed header).
            raise PermissionDenied(
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Admin panel", charset="UTF-8"'},
            ) from exc

        # Compare the provided credentials with the expected basic_string using
        # `secrets.compare_digest` for constant-time comparison to prevent timing attacks.
        if not secrets.compare_digest(credentials, self.basic_string):
            # If credentials do not match, raise PermissionDenied.
            raise PermissionDenied(
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Admin panel", charset="UTF-8"'},
            )

        # If authentication is successful, pass the request to the wrapped ASGI application.
        await self.app(scope, receive, send)
