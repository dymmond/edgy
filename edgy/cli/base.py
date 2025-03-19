import argparse
import inspect
import os
import typing
import warnings
from collections.abc import Awaitable, Callable
from importlib import import_module
from typing import TYPE_CHECKING, Any, Optional, Union, cast

from alembic import __version__ as __alembic_version__
from alembic import command
from alembic.config import Config as AlembicConfig

import edgy
from edgy.cli.constants import DEFAULT_TEMPLATE_NAME
from edgy.cli.decorators import catch_errors
from edgy.core.db.context_vars import with_force_fields_nullable
from edgy.core.signals import post_migrate, pre_migrate
from edgy.utils.compat import is_class_and_subclass

if TYPE_CHECKING:
    from edgy.core.connection.registry import Registry

alembic_version = tuple(int(v) for v in __alembic_version__.split(".")[0:3])


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

    @classmethod
    def get_instance(
        cls,
        args: Optional[typing.Sequence] = None,
        options: Optional[typing.Any] = None,
    ) -> Any:
        directory = str(edgy.settings.migration_directory)
        config = cls(os.path.join(directory, "alembic.ini"))
        config.set_main_option("script_location", str(directory))

        if config.cmd_opts is None:
            config.cmd_opts = argparse.Namespace()

        for option in options or []:
            setattr(config.cmd_opts, option, True)

        if not hasattr(config.cmd_opts, "x"):
            if args is not None:
                config.cmd_opts.x = []
                if isinstance(args, (list, tuple)):
                    for arg in args:
                        config.cmd_opts.x.append(arg)
                else:
                    config.cmd_opts.x.append(args)
            else:
                config.cmd_opts.x = None
        return config


def _async_wrapper(fn: Callable[..., Awaitable]) -> Callable:
    def _(*args: Any, **kwargs: Any) -> None:
        edgy.run_sync(fn(*args, **kwargs))

    return _


class Migrate:
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
        model_apps: Union[dict[str, str], tuple[str], list[str], None] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__()

        self.app = app
        self.registry = registry
        self.model_apps = model_apps or {}

        assert isinstance(self.model_apps, (dict, tuple, list)), (
            "`model_apps` must be a dict of 'app_name:location' format or a list/tuple of strings."
        )

        if isinstance(self.model_apps, dict):
            self.model_apps = cast(dict[str, str], self.model_apps.values())

        models = self.check_db_models(self.model_apps)

        for name, value in models.items():
            if name in self.registry.models:
                warnings.warn(
                    f"There is already a model with the name {name} declared. Overriding the model will occur unless you rename it.",
                    stacklevel=2,
                )
            # proper add to registry
            value.add_to_registry(self.registry, database="keep", on_conflict="replace")
        self.set_edgy_extension(app)

    def check_db_models(
        self, model_apps: Union[dict[str, str], tuple[str], list[str]]
    ) -> dict[str, Any]:
        """
        Goes through all the model applications declared in the migrate and
        adds them into the registry.
        """
        from edgy.core.db.models import Model, ReflectModel

        models: dict[str, Any] = {}

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
        edgy.monkay.set_instance(edgy.Instance(self.registry, self.app))


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
    template: Optional[str] = None,
    package: bool = False,
) -> None:
    """Creates a new migration folder"""
    directory = str(edgy.monkay.settings.migration_directory)

    template_directory = None

    if template is not None and ("/" in template or "\\" in template):
        template_directory, template = os.path.split(template)

    config = Config(template_directory=template_directory)
    config.set_main_option("script_location", directory)
    config.config_file_name = os.path.join(directory, "alembic.ini")

    if template is None:
        template = DEFAULT_TEMPLATE_NAME
    command.init(config, directory, template, package)


@catch_errors
def revision(
    message: Optional[str] = None,
    autogenerate: bool = False,
    sql: bool = False,
    head: str = "head",
    splice: bool = False,
    branch_label: Optional[str] = None,
    version_path: Optional[str] = None,
    revision_id: Optional[typing.Any] = None,
    arg: Optional[typing.Any] = None,
    null_fields: Union[list[str], tuple[str, ...]] = (),
) -> None:
    """
    Creates a new revision file
    """
    options = ["autogenerate"] if autogenerate else None
    config = Config.get_instance(options=options, args=arg)
    with with_force_fields_nullable(null_fields):
        pre_migrate.send(
            "revision",
            _async_wrapper=_async_wrapper,
            config=config,
            message=message,
            autogenerate=autogenerate,
            sql=sql,
            head=head,
            splice=splice,
            branch_label=branch_label,
            version_path=version_path,
            revision_id=revision_id,
        )
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
        post_migrate.send(
            "revision",
            _async_wrapper=_async_wrapper,
            config=config,
            message=message,
            autogenerate=autogenerate,
            sql=sql,
            head=head,
            splice=splice,
            branch_label=branch_label,
            version_path=version_path,
            revision_id=revision_id,
        )


def migrate(
    message: Optional[str] = None,
    sql: bool = False,
    head: str = "head",
    splice: bool = False,
    branch_label: Optional[str] = None,
    version_path: Optional[str] = None,
    revision_id: Optional[typing.Any] = None,
    arg: Optional[typing.Any] = None,
    null_fields: Union[list[str], tuple[str, ...]] = (),
) -> None:
    """Alias for 'revision --autogenerate'"""
    return revision(
        message=message,
        autogenerate=True,
        sql=sql,
        head=head,
        splice=splice,
        branch_label=branch_label,
        version_path=version_path,
        revision_id=revision_id,
        arg=arg,
        null_fields=null_fields,
    )


@catch_errors
def edit(revision: str = "current") -> None:
    """Edit current revision."""
    if alembic_version >= (1, 9, 4):
        config = Config.get_instance()
        command.edit(config, revision)
    else:
        raise RuntimeError("Alembic 1.9.4 or greater is required")


@catch_errors
def merge(
    revisions: str = "",
    message: Optional[str] = None,
    branch_label: Optional[str] = None,
    revision_id: Optional[str] = None,
) -> None:
    """Merge two revisions together.  Creates a new migration file"""
    config = Config.get_instance()
    command.merge(
        config, revisions, message=message, branch_label=branch_label, rev_id=revision_id
    )


@catch_errors
def upgrade(
    revision: str = "head",
    sql: bool = False,
    tag: Optional[str] = None,
    arg: Optional[typing.Any] = None,
) -> None:
    """Upgrade to a later version"""
    config = Config.get_instance(args=arg)
    pre_migrate.send(
        "upgrade",
        _async_wrapper=_async_wrapper,
        config=config,
        revision=revision,
        sql=sql,
        tag=tag,
    )
    command.upgrade(config, revision, sql=sql, tag=tag)
    post_migrate.send(
        "upgrade",
        _async_wrapper=_async_wrapper,
        config=config,
        revision=revision,
        sql=sql,
        tag=tag,
    )


@catch_errors
def downgrade(
    revision: str = "-1",
    sql: bool = False,
    tag: Optional[str] = None,
    arg: Optional[typing.Any] = None,
) -> None:
    """Revert to a previous version"""
    config = Config.get_instance(args=arg)
    if sql and revision == "-1":
        revision = "head:-1"
    pre_migrate.send(
        "downgrade",
        _async_wrapper=_async_wrapper,
        config=config,
        revision=revision,
        sql=sql,
        tag=tag,
    )
    command.downgrade(config, revision, sql=sql, tag=tag)
    post_migrate.send(
        "downgrade",
        _async_wrapper=_async_wrapper,
        config=config,
        revision=revision,
        sql=sql,
        tag=tag,
    )


@catch_errors
def show(
    revision: str = "head",
) -> None:
    """Show the revision denoted by the given symbol."""
    config = Config.get_instance()
    command.show(config, revision)


@catch_errors
def history(
    rev_range: Optional[typing.Any] = None,
    verbose: bool = False,
    indicate_current: bool = False,
) -> None:
    """List changeset scripts in chronological order."""
    config = Config.get_instance()
    command.history(config, rev_range, verbose=verbose, indicate_current=indicate_current)


@catch_errors
def heads(
    verbose: bool = False,
    resolve_dependencies: bool = False,
) -> None:
    """Show current available heads in the script directory"""
    config = Config.get_instance()
    command.heads(config, verbose=verbose, resolve_dependencies=resolve_dependencies)


@catch_errors
def branches(verbose: bool = False) -> None:
    """Show current branch points"""
    config = Config.get_instance()
    command.branches(config, verbose=verbose)


@catch_errors
def current(verbose: bool = False) -> None:
    """Display the current revision for each database."""
    config = Config.get_instance()
    command.current(config, verbose=verbose)


@catch_errors
def stamp(
    revision: str = "head",
    sql: bool = False,
    tag: Optional[typing.Any] = None,
) -> None:
    """'stamp' the revision table with the given revision; don't run any
    migrations"""
    config = Config.get_instance()
    command.stamp(config, revision, sql=sql, tag=tag)


@catch_errors
def check() -> None:
    """Check if there are any new operations to migrate"""
    config = Config.get_instance()
    command.check(config)
