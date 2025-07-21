from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from lilya import status
from lilya.apps import ChildLilya, Lilya
from lilya.middleware import DefineMiddleware
from lilya.middleware.session_context import SessionContextMiddleware
from lilya.requests import Request
from lilya.routing import RoutePath
from lilya.templating import Jinja2Template

from edgy.contrib.lilya.middleware import EdgyMiddleware

from .views import (
    AdminDashboard,
    JSONSchemaView,
    ModelDetailView,
    ModelObjectCreateView,
    ModelObjectDeleteView,
    ModelObjectDetailView,
    ModelObjectEditView,
    ModelOverview,
)

if TYPE_CHECKING:
    from edgy.conf.global_settings import EdgySettings
    from edgy.core.connection import Registry

# Initialize Jinja2Template to load templates from the 'templates' directory
# relative to the current file.
templates = Jinja2Template(directory=str(Path(__file__).resolve().parent / "templates"))
# Add the built-in 'getattr' function to Jinja2's global environment.
# This allows 'getattr' to be used directly within templates for dynamic attribute access.
templates.env.globals["getattr"] = getattr


async def not_found(request: Request, exc: Exception) -> Any:
    """
    An asynchronous exception handler for 404 Not Found errors.

    This function renders a 404.html template and returns it with a 404 status code.

    Args:
        request (Request): The incoming Lilya request object.
        exc (Exception): The exception that triggered this handler (e.g., NotFound).

    Returns:
        Any: A Jinja2TemplateResponse object for the 404 page.
    """
    return templates.get_template_response(
        request, "404.html", context={"title": "Not Found"}, status_code=status.HTTP_404_NOT_FOUND
    )


def create_admin_app(
    *,
    session_sub_path: str = "",
    registry: Registry | None = None,
    settings: EdgySettings | None = None,
) -> Lilya:
    """
    Creates and configures a Lilya application for the Edgy administrative interface.

    This function sets up routes for various admin functionalities like dashboard,
    model overview, model details, creation, editing, and deletion. It also
    integrates Edgy-specific middleware and session management.

    Args:
        session_sub_path (str, optional): The sub-path for the session cookie.
                                          Useful when the application is mounted
                                          under a sub-directory. Defaults to "".
        registry (Registry | None, optional): An Edgy Registry instance to be used
                                              by the admin application for database
                                              operations. Defaults to None.
        settings (EdgySettings | None, optional): An EdgySettings instance to be used
                                                  by the admin application.
                                                  Defaults to None.

    Returns:
        Lilya: A configured Lilya application instance ready to serve the admin interface.
    """
    # Define the list of middleware to be applied to the admin application.
    middleware: list[DefineMiddleware] = [
        # EdgyMiddleware integrates Edgy's registry and settings into the ASGI scope.
        DefineMiddleware(EdgyMiddleware, registry=registry, settings=settings),
        # SessionContextMiddleware enables session management for the application.
        DefineMiddleware(SessionContextMiddleware, sub_path=session_sub_path),
    ]
    # Create a ChildLilya application instance.
    return ChildLilya(
        routes=[
            RoutePath("/", handler=AdminDashboard, name="admin"),
            RoutePath("/models", handler=ModelOverview, name="models"),
            RoutePath("/models/{name}", handler=ModelDetailView, name="model-details"),
            RoutePath("/models/{name}/json", handler=JSONSchemaView, name="model-schema"),
            RoutePath("/models/{name}/create", handler=ModelObjectCreateView, name="model-create"),
            RoutePath("/models/{name}/{id}", handler=ModelObjectDetailView, name="model-object"),
            RoutePath(
                "/models/{name}/{id}/edit",
                handler=ModelObjectEditView,
                name="model-edit",
                methods=["GET", "POST"],
            ),
            RoutePath(
                "/models/{name}/{id}/delete",
                handler=ModelObjectDeleteView,
                name="model-delete",
                methods=["POST"],
            ),
        ],
        middleware=middleware,
        # Register the custom 404 not found handler.
        exception_handlers={404: not_found},
    )
