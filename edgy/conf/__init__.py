from typing import Any

from .global_settings import EdgySettings


class SettingsForward:
    def __getattribute__(self, name: str) -> Any:
        from edgy import monkay

        return getattr(monkay.settings, name)


settings: EdgySettings = SettingsForward()  # types: ignore

__all__ = ["settings"]
