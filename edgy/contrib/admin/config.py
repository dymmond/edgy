from __future__ import annotations

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AdminConfig(BaseSettings):
    """
    Configuration settings for the Edgy administrative interface.

    This class provides a structured way to define various customizable
    aspects of the Edgy Admin, such as URL prefixes, template paths,
    titles, branding elements, and security keys.
    """

    model_config = SettingsConfigDict(extra="allow", arbitrary_types_allowed=True)
    admin_prefix_url: str | None = None
    """
    The URL prefix under which the Edgy Admin interface will be mounted.
    If `None`, the admin will be served from the root URL.
    """
    admin_extra_templates: list[str | os.PathLike] = Field(default_factory=list)
    """
    A list of additional directories where the admin interface should
    look for custom templates. This allows for overriding or extending
    the default admin templates.
    """
    title: str = "Edgy Admin"
    """
    The main title displayed in the browser's title bar for the admin interface.
    Defaults to "Edgy Admin".
    """
    menu_title: str = "Edgy Admin"
    """
    The title displayed in the navigation menu of the admin interface.
    Defaults to "Edgy Admin".
    """
    favicon: str = "https://raw.githubusercontent.com/dymmond/edgy/refs/heads/main/docs/statics/images/favicon.ico"
    """
    The URL to the favicon for the admin interface.
    Defaults to the official Edgy favicon.
    """
    sidebar_bg_colour: str = "#1C4C74"
    """
    The background color of the sidebar in the admin interface.
    Defaults to a shade of blue (#1C4C74).
    """
    dashboard_title: str = "Edgy Admin Dashboard"
    """
    The title displayed on the main dashboard page of the admin interface.
    Defaults to "Edgy Admin Dashboard".
    """
    SECRET_KEY: str | bytes = Field(default_factory=lambda: os.urandom(64))
    """
    A secret key used for security purposes, such as signing session cookies.
    It generates a random 64-byte string by default if not explicitly set.
    """
