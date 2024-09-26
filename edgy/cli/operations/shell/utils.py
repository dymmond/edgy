import datetime
from collections import OrderedDict
from typing import Any

import pydantic

import edgy
from edgy import Registry
from edgy.core.terminal import OutputColour, Print

printer = Print()

defaults = OrderedDict()

defaults.update(
    {
        "datetime": datetime.datetime,
        "timedelta": datetime.timedelta,
        "BaseModel": pydantic.BaseModel,
        "ConfigDict": pydantic.ConfigDict,
        "settings": edgy.settings,
        "Model": edgy.Model,
        "ReflectModel": edgy.ReflectModel,
    }
)


def welcome_message(app: Any) -> None:
    """Displays the welcome message for the user"""
    now = datetime.datetime.now().strftime("%b %d %Y, %H:%M:%S")
    edgy_info_date = f"Edgy {edgy.__version__} (interactive shell, {now})"
    info = "Interactive shell that imports the application models and some python defaults."

    application_text = printer.message("Application: ", colour=OutputColour.CYAN3)
    application_name = printer.message(app.__class__.__name__, colour=OutputColour.GREEN3)
    application = f"{application_text}{application_name}"

    printer.write_plain(edgy_info_date, colour=OutputColour.CYAN3)
    printer.write_plain(info, colour=OutputColour.CYAN3)
    printer.write_plain(application)


def import_objects(app: Any, registry: Registry) -> dict[Any, Any]:
    """
    Imports all the needed objects needed for the shell.
    """
    imported_objects = {}
    import_statement = "from {module_path} import {model}"
    welcome_message(app)
    printer.write_success(79 * "-", colour=OutputColour.CYAN3)

    def import_defaults() -> None:
        for name, module in defaults.items():
            directive = import_statement.format(module_path=module.__module__, model=name)
            printer.write_success(directive, colour=OutputColour.CYAN3)
            imported_objects[name] = module

    def _import_objects(lookup_dict: dict[Any, Any]) -> None:
        for _, model in sorted(lookup_dict.items()):
            directive = import_statement.format(module_path=model.__module__, model=model.__name__)
            printer.write_success(directive, colour=OutputColour.CYAN3)
            imported_objects[model.__name__] = model

    def import_models() -> None:
        if not registry.models:
            return

        printer.write_success("Models".center(79, "-"), colour=OutputColour.CYAN3)
        _import_objects(registry.models)

    def import_reflected_models() -> None:
        if not registry.reflected:
            return

        printer.write_success("Reflected models".center(79, "-"), colour=OutputColour.CYAN3)
        _import_objects(registry.reflected)

    import_defaults()
    import_models()
    import_reflected_models()

    return imported_objects
