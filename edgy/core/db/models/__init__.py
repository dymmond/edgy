from typing import TYPE_CHECKING

from monkay import Monkay

if TYPE_CHECKING:
    from .managers import Manager, RedirectManager
    from .model import Model, ReflectModel, StrictModel
    from .model_reference import ModelRef

__all__ = ["Model", "StrictModel", "ModelRef", "ReflectModel", "Manager", "RedirectManager"]

Monkay(
    globals(),
    lazy_imports={
        "Model": ".model.Model",
        "ReflectModel": ".model.ReflectModel",
        "StrictModel": ".model.StrictModel",
        "ModelRef": ".model_reference.ModelRef",
        "Manager": ".managers.Manager",
        "RedirectManager": ".managers.RedirectManager",
    },
)
