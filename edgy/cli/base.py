import argparse
import inspect
import os
import typing
import warnings
from importlib import import_module
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, Union, cast

from alembic import __version__ as __alembic_version__
from alembic import command
from alembic.config import Config as AlembicConfig

from edgy.cli.constants import DEFAULT_TEMPLATE_NAME, EDGY_DB
from edgy.cli.decorators import catch_errors
from edgy.core.extras.base import BaseExtra
from edgy.core.utils.functional import edgy_setattr
from edgy.utils.compat import is_class_and_subclass

if TYPE_CHECKING:
    from edgy.core.connection.registry import Registry

alembic_version = tuple(int(v) for v in __alembic_version__.split(".")[0:3])


class MigrateConfig:
    def __init__(self, migrate: typing.Any, registry: "Registry", **kwargs: Any) -> None:
        self.migrate = migrate
        self.registry = registry
        self.directory = migrate.directory
        self.kwargs = kwargs

    @property
    def metadata(self) -> typing.Any:
        return self.registry.metadata


class Config(AlembicConfig):
    """
    Base configuration connecting Edgy with Alembic.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.template_directory = kwargs.pop("template_directory", None)
        super().__init__(*args, **kwargs)

    def get_template_directory(self) -> Any:
        if self.template_directory:
            return self.template_directory
        package_dir = os.path.abspath(os.path.dirname(__file__))
        return os.path.join(package_dir, "templates")


class Migrate(BaseExtra):
    """
    Main migration object that should be used in any application
    that requires Edgy to control the migration process.

    This process will always create an entry in any ASGI application
    if there isn't any.
    """

    def __init__(
        self,
        app: typing.Any,
        registry: "Registry",
        model_apps: Union[Dict[str, str], Tuple[str], List[str], None] = None,
        compare_type: bool = True,
        render_as_batch: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        self.app = app
        self.configure_callbacks: typing.List[Callable] = []
        self.registry = registry
        self.model_apps = model_apps or {}

        assert isinstance(
            self.model_apps, (dict, tuple, list)
        ), "`model_apps` must be a dict of 'app_name:location' format or a list/tuple of strings."

        if isinstance(self.model_apps, dict):
            self.model_apps = cast(Dict[str, str], self.model_apps.values())

        models = self.check_db_models(self.model_apps)

        for name, _ in models.items():
            if name in self.registry.models:
                warnings.warn(
                    f"There is already a model with the name {name} declared. Overriding the model will occur unless you rename it.",
                    stacklevel=2,
                )

        if self.registry.models:
            self.registry.models = {**models, **self.registry.models}
        else:
            self.registry.models = models

        self.directory = "migrations"
        self.alembic_ctx_kwargs = kwargs
        self.alembic_ctx_kwargs["compare_type"] = compare_type
        self.alembic_ctx_kwargs["render_as_batch"] = render_as_batch

        self.set_edgy_extension(app)

    def check_db_models(
        self, model_apps: Union[Dict[str, str], Tuple[str], List[str]]
    ) -> Dict[str, Any]:
        """
        Goes through all the model applications declared in the migrate and
        adds them into the registry.
        """
        from edgy.core.db.models import Model, ReflectModel

        models: Dict[str, Any] = {}

        for location in model_apps:
            module = import_module(location)
            members = inspect.getmembers(
                module,
                lambda attr: is_class_and_subclass(attr, Model)
                and not attr.meta.abstract
                and not is_class_and_subclass(attr, ReflectModel),
            )
            for name, model in members:
                models[name] = model
        return models

    def set_edgy_extension(self, app: Any, **kwargs: Any) -> None:
        """
        Sets a Edgy dictionary for the app object.
        """
        migrate = MigrateConfig(self, self.registry, **self.alembic_ctx_kwargs)
        edgy_setattr(app, EDGY_DB, {})
        app._edgy_db["migrate"] = migrate

    def configure(self, f: Callable) -> Any:
        self.configure_callbacks.append(f)
        return f

    def call_configure_callbacks(self, config: Config) -> Config:
        for f in self.configure_callbacks:
            config = f(config)
        return config

    def get_config(
        self,
        directory: Optional[str] = None,
        arg: Optional[typing.Any] = None,
        options: Optional[typing.Any] = None,
    ) -> Any:
        if directory is None:
            directory = self.directory
        directory = str(directory)
        config = Config(os.path.join(directory, "alembic.ini"))
        config.set_main_option("script_location", directory)

        if config.cmd_opts is None:
            config.cmd_opts = argparse.Namespace()

        for option in options or []:
            setattr(config.cmd_opts, option, True)

        if not hasattr(config.cmd_opts, "x"):
            if arg is not None:
                config.cmd_opts.x = []
                if isinstance(arg, list) or isinstance(arg, tuple):
                    for x in arg:
                        config.cmd_opts.x.append(x)
                else:
                    config.cmd_opts.x.append(arg)
            else:
                config.cmd_opts.x = None
        return self.call_configure_callbacks(config)


@catch_errors
def list_templates() -> None:
    """Lists the available templates"""
    config = Config()
    config.print_stdout("Available templates:\n")

    for name in sorted(os.listdir(config.get_template_directory())):
        with open(os.path.join(config.get_template_directory(), name, "README")) as readme:
            synopsis = next(readme).strip()
        config.print_stdout(f"{name} - {synopsis}")


@catch_errors
def init(
    app: Optional[typing.Any],
    directory: Optional[str] = None,
    template: Optional[str] = None,
    package: bool = False,
) -> None:
    """Creates a new migration folder"""
    if directory is None:
        directory = "migrations"

    template_directory = None

    if template is not None and ("/" in template or "\\" in template):
        template_directory, template = os.path.split(template)

    config = Config(template_directory=template_directory)
    config.set_main_option("script_location", directory)
    config.config_file_name = os.path.join(directory, "alembic.ini")
    config = app._edgy_db["migrate"].migrate.call_configure_callbacks(config)  # type: ignore

    if template is None:
        template = DEFAULT_TEMPLATE_NAME
    command.init(config, directory, template, package)


@catch_errors
def revision(
    app: Optional[typing.Any],
    directory: Optional[str] = None,
    message: Optional[str] = None,
    autogenerate: bool = False,
    sql: bool = False,
    head: str = "head",
    splice: bool = False,
    branch_label: Optional[str] = None,
    version_path: Optional[str] = None,
    revision_id: Optional[typing.Any] = None,
) -> None:
    """
    Creates a new revision file
    """
    options = ["autogenerate"] if autogenerate else None
    config = app._edgy_db["migrate"].migrate.get_config(directory, options)  # type: ignore

    command.revision(
        config,
        message,
        autogenerate=autogenerate,
        sql=sql,
        head=head,
        splice=splice,
        branch_label=branch_label,
        version_path=version_path,
        rev_id=revision_id,
    )


@catch_errors
def migrate(
    app: Optional[typing.Any],
    directory: Optional[str] = None,
    message: Optional[str] = None,
    sql: bool = False,
    head: str = "head",
    splice: bool = False,
    branch_label: Optional[str] = None,
    version_path: Optional[str] = None,
    revision_id: Optional[typing.Any] = None,
    arg: Optional[typing.Any] = None,
) -> None:
    """Alias for 'revision --autogenerate'"""
    config = app._edgy_db["migrate"].migrate.get_config(  # type: ignore
        directory, options=["autogenerate"], arg=arg
    )

    command.revision(
        config,
        message,
        autogenerate=True,
        sql=sql,
        head=head,
        splice=splice,
        branch_label=branch_label,
        version_path=version_path,
        rev_id=revision_id,
    )


@catch_errors
def edit(
    app: Optional[typing.Any], directory: Optional[str] = None, revision: str = "current"
) -> None:
    """Edit current revision."""
    if alembic_version >= (1, 9, 4):
        config = app._edgy_db["migrate"].migrate.get_config(directory)  # type: ignore
        command.edit(config, revision)
    else:
        raise RuntimeError("Alembic 1.9.4 or greater is required")


@catch_errors
def merge(
    app: Optional[typing.Any],
    directory: Optional[str] = None,
    revisions: str = "",
    message: Optional[str] = None,
    branch_label: Optional[str] = None,
    revision_id: Optional[str] = None,
) -> None:
    """Merge two revisions together.  Creates a new migration file"""
    config = app._edgy_db["migrate"].migrate.get_config(directory)  # type: ignore
    command.merge(
        config, revisions, message=message, branch_label=branch_label, rev_id=revision_id
    )


@catch_errors
def upgrade(
    app: Optional[typing.Any],
    directory: Optional[str] = None,
    revision: str = "head",
    sql: bool = False,
    tag: Optional[str] = None,
    arg: Optional[typing.Any] = None,
) -> None:
    """Upgrade to a later version"""
    config = app._edgy_db["migrate"].migrate.get_config(directory, arg=arg)  # type: ignore
    command.upgrade(config, revision, sql=sql, tag=tag)


@catch_errors
def downgrade(
    app: Optional[typing.Any],
    directory: Optional[str] = None,
    revision: str = "-1",
    sql: bool = False,
    tag: Optional[str] = None,
    arg: Optional[typing.Any] = None,
) -> None:
    """Revert to a previous version"""
    config = app._edgy_db["migrate"].migrate.get_config(directory, arg=arg)  # type: ignore
    if sql and revision == "-1":
        revision = "head:-1"
    command.downgrade(config, revision, sql=sql, tag=tag)


@catch_errors
def show(
    app: Optional[typing.Any],
    directory: Optional[str] = None,
    revision: str = "head",
) -> None:
    """Show the revision denoted by the given symbol."""
    config = app._edgy_db["migrate"].migrate.get_config(directory)  # type: ignore
    command.show(config, revision)  # type: ignore


@catch_errors
def history(
    app: Optional[typing.Any],
    directory: Optional[str] = None,
    rev_range: Optional[typing.Any] = None,
    verbose: bool = False,
    indicate_current: bool = False,
) -> None:
    """List changeset scripts in chronological order."""
    config = app._edgy_db["migrate"].migrate.get_config(directory)  # type: ignore
    command.history(config, rev_range, verbose=verbose, indicate_current=indicate_current)


@catch_errors
def heads(
    app: Optional[typing.Any],
    directory: Optional[str] = None,
    verbose: bool = False,
    resolve_dependencies: bool = False,
) -> None:
    """Show current available heads in the script directory"""
    config = app._edgy_db["migrate"].migrate.get_config(directory)  # type: ignore
    command.heads(config, verbose=verbose, resolve_dependencies=resolve_dependencies)  # type: ignore


@catch_errors
def branches(
    app: Optional[typing.Any], directory: Optional[str] = None, verbose: bool = False
) -> None:
    """Show current branch points"""
    config = app._edgy_db["migrate"].migrate.get_config(directory)  # type: ignore
    command.branches(config, verbose=verbose)  # type: ignore


@catch_errors
def current(
    app: Optional[typing.Any], directory: Optional[str] = None, verbose: bool = False
) -> None:
    """Display the current revision for each database."""
    config = app._edgy_db["migrate"].migrate.get_config(directory)  # type: ignore
    command.current(config, verbose=verbose)


@catch_errors
def stamp(
    app: Optional[typing.Any],
    directory: Optional[str] = None,
    revision: str = "head",
    sql: bool = False,
    tag: Optional[typing.Any] = None,
) -> None:
    """'stamp' the revision table with the given revision; don't run any
    migrations"""
    config = app._edgy_db["migrate"].migrate.get_config(directory)  # type: ignore
    command.stamp(config, revision, sql=sql, tag=tag)


@catch_errors
def check(
    app: Optional[typing.Any],
    directory: Optional[str] = None,
) -> None:
    """Check if there are any new operations to migrate"""
    config = app._edgy_db["migrate"].migrate.get_config(directory)  # type: ignore
    command.check(config)
