import os
import sys
import typing
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path

from edgy.cli.constants import (
    DISCOVERY_FILES,
    DISCOVERY_FUNCTIONS,
    EDGY_DB,
    EDGY_DISCOVER_APP,
    EDGY_EXTRA,
)
from edgy.exceptions import CommandEnvironmentError


@dataclass
class Scaffold:
    """
    Simple Application scaffold that holds the
    information about the app and the path to
    the same app.
    """

    path: str
    app: typing.Any


@dataclass
class MigrationEnv:
    """
    Loads an arbitraty application into the object
    and returns the App.
    """

    path: typing.Optional[str] = None
    app: typing.Optional[typing.Any] = None
    command_path: typing.Optional[str] = None

    def load_from_env(
        self, path: typing.Optional[str] = None, enable_logging: bool = True
    ) -> "MigrationEnv":
        """
        Loads the environment variables into the scaffold.
        """
        # Adds the current path where the command is being invoked
        # To the system path
        cwd = Path().cwd()
        command_path = str(cwd)
        if command_path not in sys.path:
            sys.path.append(command_path)
        try:
            import dotenv

            dotenv.load_dotenv()
        except ImportError:
            ...

        _path = path if path else os.getenv(EDGY_DISCOVER_APP)
        _app = self.find_app(path=_path, cwd=cwd)

        return MigrationEnv(path=_app.path, app=_app.app)

    def import_app_from_string(cls, path: typing.Optional[str] = None) -> Scaffold:
        if path is None:
            raise CommandEnvironmentError(
                detail="Path cannot be None. Set env `EDGY_DEFAULT_APP` or use `--app` instead."
            )
        module_str_path, app_name = path.split(":")
        module = import_module(module_str_path)
        app = getattr(module, app_name)
        return Scaffold(path=path, app=app)

    def _find_app_in_folder(  # type: ignore
        self, path: Path, cwd: Path
    ) -> typing.Union[typing.Callable[..., typing.Any], Scaffold, None]:
        """
        Iterates inside the folder and looks up to the DISCOVERY_FILES.
        """
        for discovery_file in DISCOVERY_FILES:
            file_path = path / discovery_file
            if not file_path.exists():
                continue

            dotted_path = ".".join(file_path.relative_to(cwd).with_suffix("").parts)

            # Load file from module
            module = import_module(dotted_path)

            # Iterates through the elements of the module.
            for attr, value in module.__dict__.items():
                if callable(value) and (hasattr(value, EDGY_DB) or hasattr(value, EDGY_EXTRA)):
                    app_path = f"{dotted_path}:{attr}"
                    return Scaffold(app=value, path=app_path)

            # Iterate over default pattern application functions
            for func in DISCOVERY_FUNCTIONS:
                if hasattr(module, func):
                    app_path = f"{dotted_path}:{func}"
                    fn = getattr(module, func)()

                    if hasattr(fn, EDGY_DB) or hasattr(fn, EDGY_EXTRA):
                        return Scaffold(app=fn, path=app_path)

    def find_app(self, path: typing.Optional[str], cwd: Path) -> Scaffold:
        """
        Loads the application based on the path provided via env var.

        If no --app is provided, goes into auto discovery up to one level.
        """

        if path:
            return self.import_app_from_string(path)

        scaffold: typing.Optional[Scaffold] = None

        # Check current folder
        scaffold = self._find_app_in_folder(cwd, cwd)  # type: ignore
        if scaffold:
            return scaffold

        # Goes into auto discovery mode for one level, only.

        for folder in cwd.iterdir():
            folder_path = cwd / folder
            scaffold = self._find_app_in_folder(folder_path, cwd)  # type: ignore

            if not scaffold:
                continue
            break

        if not scaffold:
            raise CommandEnvironmentError(detail="Could not find Edgy in any application.")
        return scaffold
