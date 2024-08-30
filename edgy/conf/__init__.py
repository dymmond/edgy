import os
from typing import Any

from edgy.conf.functional import LazyObject, empty
from edgy.conf.module_import import import_string

ENVIRONMENT_VARIABLE = "EDGY_SETTINGS_MODULE"


class EdgyLazySettings(LazyObject):
    def _setup(self) -> None:
        """
        Load the settings module pointed to by the environment variable. This
        is used the first time settings are needed, if the user hasn't
        configured settings manually.
        """
        settings_module: str = os.environ.get(
            ENVIRONMENT_VARIABLE, "edgy.conf.global_settings.EdgySettings"
        )
        settings: Any = import_string(settings_module)

        for setting, _ in settings().model_dump().items():
            assert setting.islower(), f"{setting} should be in lowercase."

        self._wrapped = settings()

    def __repr__(self) -> str:
        # Hardcode the class name as otherwise it yields 'Settings'.
        if self._wrapped is empty:
            return "<EdgyLazySettings [Unevaluated]>"
        return f'<EdgyLazySettings "{self._wrapped.__class__.__name__}">'

    @property
    def configured(self) -> Any:
        """Return True if the settings have already been configured."""
        return self._wrapped is not empty


settings: EdgyLazySettings = EdgyLazySettings()


__all__ = ["EdgyLazySettings", "settings"]
