import datetime
from importlib import import_module
from typing import Any

from monkay import load

import edgy
from edgy import Registry
from edgy.core.terminal import OutputColour, Print

printer = Print()

defaults = {
    "edgy": "edgy",
    "datetime": "datetime:datetime",
    "timedelta": "datetime:timedelta",
    "BaseModel": "pydantic:BaseModel",
    "ConfigDict": "pydantic:ConfigDict",
    "settings": "edgy.conf:settings",
    "Instance": "edgy:Instance",
    "Model": "edgy:Model",
    "ReflectModel": "edgy:ReflectModel",
}


def welcome_message(app: Any) -> None:
    """Displays the welcome message for the user"""
    now = datetime.datetime.now().strftime("%b %d %Y, %H:%M:%S")
    edgy_info_date = f"Edgy {edgy.__version__} (interactive shell, {now})"
    info = "Interactive shell that imports the application models and some python defaults."

    printer.write_plain(edgy_info_date, colour=OutputColour.CYAN3)
    printer.write_plain(info, colour=OutputColour.CYAN3)
    if app is not None:
        unwrapped_app = app
        while uwrapped := getattr(unwrapped_app, "__wrapped__", None):
            unwrapped_app = uwrapped
        application_text = printer.message("Application: ", colour=OutputColour.CYAN3)
        application_name = printer.message(
            type(unwrapped_app).__name__, colour=OutputColour.GREEN3
        )
        printer.write_plain(f"{application_text}{application_name}")


def import_objects(app: Any, registry: Registry) -> dict[str, Any]:
    """
    Imports all the needed objects needed for the shell.
    """
    imported_objects = {}
    direct_import_statement = "import {import_path}"
    import_statement1 = "from {module_path} import {model}"
    import_statement2 = "from {module_path} import {model} as {name}"
    welcome_message(app)
    printer.write_success(79 * "-", colour=OutputColour.CYAN3)

    def import_defaults() -> None:
        for name, import_path in defaults.items():
            splitted = import_path.rsplit(":", 1)
            if len(splitted) == 2:
                directive = (
                    import_statement1 if splitted[1] == name else import_statement2
                ).format(module_path=splitted[0], model=splitted[1], name=name)
                imported_objects[name] = load(import_path, allow_splits=":")
            else:
                directive = direct_import_statement.format(import_path=import_path)
                imported_objects[name] = import_module(import_path)
            printer.write_success(directive, colour=OutputColour.CYAN3)

    import_model_statement = "from {module_path} import {model}"

    def _import_models(lookup_dict: dict[str, Any]) -> None:
        for name, model in sorted(lookup_dict.items()):
            # only import models which are in the admin, exclude this way through models
            if name not in registry.admin_models:
                continue
            directive = import_model_statement.format(module_path=model.__module__, model=name)
            printer.write_success(directive, colour=OutputColour.CYAN3)
            imported_objects[name] = model

    def import_models() -> None:
        if not registry.models:
            return

        printer.write_success("Models".center(79, "-"), colour=OutputColour.CYAN3)
        _import_models(registry.models)

    def import_reflected_models() -> None:
        if not registry.reflected:
            return

        printer.write_success("Reflected models".center(79, "-"), colour=OutputColour.CYAN3)
        _import_models(registry.reflected)

    import_defaults()
    import_models()
    import_reflected_models()

    return imported_objects
