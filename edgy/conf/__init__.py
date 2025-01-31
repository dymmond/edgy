from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from monkay import Monkay

    from edgy import EdgySettings, Instance


@lru_cache
def get_edgy_monkay() -> Monkay[Instance, EdgySettings]:
    from edgy import monkay

    monkay.evaluate_settings(on_conflict="error", ignore_import_errors=False)

    return monkay


class SettingsForward:
    def __getattribute__(self, name: str) -> Any:
        monkay = get_edgy_monkay()
        return getattr(monkay.settings, name)


settings: EdgySettings = cast("EdgySettings", SettingsForward())


def evaluate_settings_once_ready() -> None:
    """
    Call when settings must be ready.

    This doesn't prevent the settings being updated later or set before.
    """
    get_edgy_monkay()


__all__ = ["settings", "evaluate_settings_once_ready"]
