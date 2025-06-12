import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AdminConfig(BaseSettings):
    model_config = SettingsConfigDict(extra="allow", arbitrary_types_allowed=True)
    admin_prefix_url: str | None = None
    admin_extra_templates: list[str | os.PathLike] = Field(default_factory=list)
    title: str = "Edgy Admin"
    menu_title: str = "Edgy Admin"
    favicon: str = "https://raw.githubusercontent.com/dymmond/edgy/refs/heads/main/docs/statics/images/favicon.ico"
    sidebar_bg_colour: str = "#1C4C74"
    dashboard_title: str = "Edgy Admin Dashboard"
    SECRET_KEY: str | bytes = Field(default_factory=lambda: os.urandom(64))
