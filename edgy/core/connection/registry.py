from __future__ import annotations

import asyncio
import contextlib
import re
import warnings
from collections import defaultdict
from collections.abc import Callable, Container, Generator, Iterable, Mapping, Sequence
from copy import copy as shallow_copy
from functools import cached_property, partial
from types import TracebackType
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast, overload

import sqlalchemy
from loguru import logger
from sqlalchemy import Engine
from sqlalchemy.ext.asyncio.engine import AsyncEngine
from sqlalchemy.orm import declarative_base as sa_declarative_base

from edgy.core.connection.database import Database, DatabaseURL
from edgy.core.connection.schemas import Schema
from edgy.core.db.context_vars import CURRENT_INSTANCE, FORCE_FIELDS_NULLABLE
from edgy.core.utils.sync import current_eventloop, run_sync
from edgy.types import Undefined

from .asgi import ASGIApp, ASGIHelper

if TYPE_CHECKING:
    from edgy.conf.global_settings import EdgySettings
    from edgy.contrib.autoreflection.models import AutoReflectModel
    from edgy.core.db.models.types import BaseModelType


class MetaDataDict(defaultdict[str, sqlalchemy.MetaData]):
    """
    A specialized dictionary for managing SQLAlchemy MetaData objects, keyed by
    database names (or None for the default database). This dictionary ensures
    that only registered extra database names are accessed and provides a
    shallow copy mechanism for its contents.
    """

    def __init__(self, registry: Registry) -> None:
        """
        Initializes the MetaDataDict with a reference to the parent Registry.

        Args:
            registry (Registry): The parent Registry instance to which this
                                 MetaDataDict belongs.
        """
        self.registry = registry
        super().__init__(sqlalchemy.MetaData)

    def __getitem__(self, key: str | None) -> sqlalchemy.MetaData:
        """
        Retrieves the MetaData object associated with the given key.

        Raises:
            KeyError: If the key (database name) is not registered in the
                      registry's extra databases and is not None (for the
                      default database).

        Returns:
            sqlalchemy.MetaData: The SQLAlchemy MetaData object.
        """
        # Ensure that only registered extra database names or None are accessed.
        if key not in self.registry.extra and key is not None:
            raise KeyError(f'Extra database "{key}" does not exist.')
        return super().__getitem__(key)

    def get(self, key: str, default: Any = None) -> sqlalchemy.MetaData:
        """
        Retrieves the MetaData object for the given key, returning a default
        value if the key is not found.

        Args:
            key (str): The name of the database.
            default (Any): The default value to return if the key is not found.
                           Defaults to None.

        Returns:
            sqlalchemy.MetaData: The SQLAlchemy MetaData object or the default
                                 value.
        """
        try:
            return self[key]
        except KeyError:
            return default

    def __copy__(self) -> MetaDataDict:
        """
        Creates a shallow copy of the MetaDataDict.

        Returns:
            MetaDataDict: A new MetaDataDict instance with shallow-copied
                          MetaData objects.
        """
        _copy = MetaDataDict(registry=self.registry)
        for k, v in self.items():
            _copy[k] = shallow_copy(v)
        return _copy

    copy = __copy__


class MetaDataByUrlDict(dict):
    """
    A specialized dictionary for mapping database URLs to database names (keys
    in the `extra` registry attribute), and then retrieving the corresponding
    SQLAlchemy MetaData objects via `metadata_by_name`. This allows lookup of
    metadata based on the database connection URL.
    """

    def __init__(self, registry: Registry) -> None:
        """
        Initializes the MetaDataByUrlDict with a reference to the parent
        Registry and populates itself.

        Args:
            registry (Registry): The parent Registry instance.
        """
        self.registry = registry
        super().__init__()
        self.process()

    def process(self) -> None:
        """
        Populates the dictionary with database URLs as keys and their
        corresponding names (from `registry.extra`) as values. The default
        database URL is mapped to `None`.
        """
        self.clear()
        self[str(self.registry.database.url)] = None
        for k, v in self.registry.extra.items():
            self.setdefault(str(v.url), k)

    def __getitem__(self, key: str) -> sqlalchemy.MetaData:
        """
        Retrieves the SQLAlchemy MetaData object for the given database URL.

        Args:
            key (str): The database URL.

        Raises:
            Exception: If the internal `metadata_by_name` lookup fails.

        Returns:
            sqlalchemy.MetaData: The SQLAlchemy MetaData object.
        """
        translation_name = super().__getitem__(key)
        try:
            # Retrieve the MetaData object using the translated name from
            # metadata_by_name.
            return self.registry.metadata_by_name[translation_name]
        except KeyError as exc:
            raise Exception("metadata_by_name returned exception") from exc

    def get(self, key: str, default: Any = None) -> sqlalchemy.MetaData:
        """
        Retrieves the MetaData object for the given key (URL), returning a
        default value if the key is not found.

        Args:
            key (str): The database URL.
            default (Any): The default value to return if the key is not found.
                           Defaults to None.

        Returns:
            sqlalchemy.MetaData: The SQLAlchemy MetaData object or the default
                                 value.
        """
        try:
            return self[key]
        except KeyError:
            return default

    def get_name(self, key: str) -> str | None:
        """
        Returns the name associated with a given database URL, or raises a
        KeyError if the URL is not found.

        Args:
            key (str): The database URL.

        Returns:
            str | None: The name of the database (None for the default database).

        Raises:
            KeyError: If the URL is not found in the dictionary.
        """
        return cast(str | None, super().__getitem__(key))

    def __copy__(self) -> MetaDataByUrlDict:
        """
        Creates a shallow copy of the MetaDataByUrlDict.

        Returns:
            MetaDataByUrlDict: A new MetaDataByUrlDict instance.
        """
        return MetaDataByUrlDict(registry=self.registry)

    copy = __copy__


class Registry:
    """
    The command center for the models of Edgy. This class manages database
    connections, model registration, lifecycle callbacks, and ASGI integration.

    It serves as a central point for defining and interacting with Edgy models
    across potentially multiple database connections and schemas.
    """

    model_registry_types: ClassVar[tuple[str, ...]] = (
        "models",
        "reflected",
        "tenant_models",
        "pattern_models",
    )
    db_schema: str | None = None
    content_type: type[BaseModelType] | None = None
    dbs_reflected: set[str | None]

    def __init__(
        self,
        database: Database | str | DatabaseURL,
        *,
        with_content_type: bool | type[BaseModelType] = False,
        schema: str | None = None,
        extra: Mapping[str, Database | str] | None = None,
        automigrate_config: EdgySettings | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Initializes a new Registry instance.

        Args:
            database (Database | str | DatabaseURL): The primary database
                                                     connection. Can be a
                                                     Database instance, a
                                                     connection string, or a
                                                     DatabaseURL.
            with_content_type (bool | type[BaseModelType]): If True, enables
                content type support using Edgy's default ContentType model.
                If a BaseModelType is provided, it will be used as the
                ContentType model. Defaults to False.
            schema (str | None): The default database schema to use for models
                                 registered with this registry. Defaults to None.
            extra (Mapping[str, Database | str] | None): A dictionary of
                additional named database connections. Keys are names, values
                are Database instances or connection strings. Defaults to None.
            automigrate_config (EdgySettings | None): Configuration settings
                                                     for automatic migrations.
                                                     If provided, migrations
                                                     will be run on connection.
                                                     Defaults to None.
            **kwargs (Any): Additional keyword arguments passed to the Database
                            constructor if `database` is a string or DatabaseURL.
        """
        self.db_schema = schema
        self._automigrate_config = automigrate_config
        self._is_automigrated: bool = False
        extra = extra or {}
        self.database: Database = (
            database if isinstance(database, Database) else Database(database, **kwargs)
        )
        self.models: dict[str, type[BaseModelType]] = {}
        self.admin_models: set[str] = set()  # Set later during adding to registry
        self.reflected: dict[str, type[BaseModelType]] = {}
        self.tenant_models: dict[str, type[BaseModelType]] = {}
        self.pattern_models: dict[str, type[AutoReflectModel]] = {}
        self.dbs_reflected = set()

        self.schema = Schema(registry=self)
        # when setting a Model or Reflected Model execute the callbacks
        # Note: they are only executed if the Model is not in Registry yet
        self._onetime_callbacks: dict[str | None, list[Callable[[type[BaseModelType]], None]]] = (
            defaultdict(list)
        )
        self._callbacks: dict[str | None, list[Callable[[type[BaseModelType]], None]]] = (
            defaultdict(list)
        )

        self.extra: dict[str, Database] = {
            k: v if isinstance(v, Database) else Database(v) for k, v in extra.items()
        }
        # Validate names for extra databases.
        # we want to get all problems before failing.
        assert all([self.extra_name_check(x) for x in self.extra]), (  # noqa
            "Invalid name in extra detected. See logs for details."
        )
        self.metadata_by_url = MetaDataByUrlDict(registry=self)

        if with_content_type is not False:
            self._set_content_type(with_content_type)

    async def apply_default_force_nullable_fields(
        self,
        *,
        force_fields_nullable: Iterable[tuple[str, str]] | None = None,
        model_defaults: dict[str, dict[str, Any]] | None = None,
        filter_db_url: str | None = None,
        filter_db_name: str | None = None,
    ) -> None:
        """
        Applies default values to nullable fields in models, primarily used
        for online migrations.

        Args:
            force_fields_nullable (Iterable[tuple[str, str]] | None): A
                collection of (model_name, field_name) tuples for which default
                values should be applied. If None, uses values from
                `FORCE_FIELDS_NULLABLE` context variable.
            model_defaults (dict[str, dict[str, Any]] | None): A dictionary
                mapping model names to dictionaries of field_name: default_value
                pairs. These defaults will override existing field defaults.
            filter_db_url (str | None): If provided, only applies defaults to
                                        models connected to this specific
                                        database URL.
            filter_db_name (str | None): If provided, only applies defaults to
                                        models connected to this specific named
                                        extra database. Takes precedence over
                                        `filter_db_url`.
        """
        # Initialize force_fields_nullable from context var if not provided.
        if force_fields_nullable is None:
            force_fields_nullable = set(FORCE_FIELDS_NULLABLE.get())
        else:
            force_fields_nullable = set(force_fields_nullable)
        # Initialize model_defaults.
        if model_defaults is None:
            model_defaults = {}
        # Add model_defaults to force_fields_nullable.
        for model_name, defaults in model_defaults.items():
            for default_name in defaults:
                force_fields_nullable.add((model_name, default_name))
        # For empty model names, expand to include all matching models.
        for item in list(force_fields_nullable):
            if not item[0]:  # If model name is empty string.
                force_fields_nullable.discard(item)
                for model in self.models.values():
                    if item[1] in model.meta.fields:
                        force_fields_nullable.add((model.__name__, item[1]))

        if not force_fields_nullable:
            return  # No fields to process, exit early.

        # Determine the database URL to filter by.
        if isinstance(filter_db_name, str):
            if filter_db_name:
                filter_db_url = str(self.extra[filter_db_name].url)
            else:
                filter_db_url = str(self.database.url)

        models_with_fields: dict[str, set[str]] = {}
        # Populate models_with_fields with models and their relevant fields.
        for item in force_fields_nullable:
            if item[0] not in self.models:
                continue
            if item[1] not in self.models[item[0]].meta.fields:
                continue
            # Check if field has a default or if an override default is provided.
            if not self.models[item[0]].meta.fields[item[1]].has_default():
                overwrite_default = model_defaults.get(item[0]) or {}
                if item[1] not in overwrite_default:
                    continue
            field_set = models_with_fields.setdefault(item[0], set())
            field_set.add(item[1])

        if not models_with_fields:
            return  # No valid models/fields to update, exit early.

        ops = []
        # Iterate through models and their fields to create update operations.
        for model_name, field_set in models_with_fields.items():
            model = self.models[model_name]
            if filter_db_url and str(model.database.url) != filter_db_url:
                continue  # Skip if database URL does not match filter.

            model_specific_defaults = model_defaults.get(model_name) or {}
            filter_kwargs = dict.fromkeys(field_set)

            async def wrapper_fn(
                _model: type[BaseModelType] = model,
                _model_specific_defaults: dict = model_specific_defaults,
                _filter_kwargs: dict = filter_kwargs,
                _field_set: set[str] = field_set,
            ) -> None:
                # To reduce memory usage, only retrieve pknames and load per object.
                # Load all at once to prevent cursor interference with updates.
                query = _model.query.filter(**_filter_kwargs).only(*_model.pknames)
                for obj in await query:
                    await obj.load()  # Load the full object data.
                    # Extract database fields, excluding those in _field_set.
                    kwargs = {
                        k: v for k, v in obj.extract_db_fields().items() if k not in _field_set
                    }
                    kwargs.update(_model_specific_defaults)  # Apply specific defaults.
                    # We serialize per table to avoid transaction interlocking errors.
                    # Also, tables can become very large.
                    token = CURRENT_INSTANCE.set(query)
                    try:
                        await obj._update(
                            False,  # is_partial=False
                            kwargs,
                            # Pre-update signal for migrations.
                            pre_fn=partial(
                                _model.meta.signals.pre_update.send_async,
                                is_update=True,
                                is_migration=True,
                            ),
                            # Post-update signal for migrations.
                            post_fn=partial(
                                _model.meta.signals.post_update.send_async,
                                is_update=True,
                                is_migration=True,
                            ),
                            instance=query,
                        )
                    finally:
                        CURRENT_INSTANCE.reset(token)  # Reset context variable.

            ops.append(wrapper_fn())
        await asyncio.gather(*ops)  # Run all update operations concurrently.

    def extra_name_check(self, name: Any) -> bool:
        """
        Validates the name of an extra database connection.

        Args:
            name (Any): The name to validate.

        Returns:
            bool: True if the name is valid, False otherwise. Logs errors/warnings.
        """
        if not isinstance(name, str):
            logger.error(f"Extra database name: {name!r} is not a string.")
            return False
        elif not name.strip():
            logger.error(f'Extra database name: "{name}" is empty.')
            return False

        if name.strip() != name:
            logger.warning(
                f'Extra database name: "{name}" starts or ends with whitespace characters.'
            )
        return True

    def __copy__(self) -> Registry:
        """
        Creates a shallow copy of the Registry instance, including its models
        and their metadata.

        Returns:
            Registry: A new Registry instance with copied models.
        """
        content_type: bool | type[BaseModelType] = False
        if self.content_type is not None:
            try:
                # Attempt to copy the ContentType model if it exists and is copyable.
                content_type = self.get_model(
                    "ContentType", include_content_type_attr=False
                ).copy_edgy_model()
            except LookupError:
                # Fallback to the original content_type if not found.
                content_type = self.content_type
        # Create a new Registry instance with basic settings.
        _copy = Registry(
            self.database, with_content_type=content_type, schema=self.db_schema, extra=self.extra
        )
        # Copy models from different registry types.
        for registry_type in self.model_registry_types:
            dict_models = getattr(_copy, registry_type)
            dict_models.update(
                (
                    (
                        key,
                        val.copy_edgy_model(registry=_copy),
                    )
                    for key, val in getattr(self, registry_type).items()
                    if not val.meta.no_copy and key not in dict_models
                )
            )
        _copy.dbs_reflected = set(self.dbs_reflected)  # Copy reflected databases.
        return _copy

    def _set_content_type(
        self,
        with_content_type: Literal[True] | type[BaseModelType],
        old_content_type_to_replace: type[BaseModelType] | None = None,
    ) -> None:
        """
        Configures content type support within the registry. This involves
        either creating a default ContentType model or registering a provided
        one, and then setting up callbacks to automatically add a 'content_type'
        field to other models.

        Args:
            with_content_type (Literal[True] | type[BaseModelType]): If True,
                uses the default Edgy ContentType model. If a BaseModelType,
                that model will be used as the ContentType.
            old_content_type_to_replace (type[BaseModelType] | None): An
                optional existing ContentType model that needs to be replaced
                with the new one (e.g., during registry copying).
        """
        from edgy.contrib.contenttypes.fields import BaseContentTypeField, ContentTypeField
        from edgy.contrib.contenttypes.models import ContentType
        from edgy.core.db.models.metaclasses import MetaInfo
        from edgy.core.db.relationships.related_field import RelatedField
        from edgy.core.utils.models import create_edgy_model

        # Use default ContentType if `with_content_type` is True.
        if with_content_type is True:
            with_content_type = ContentType

        real_content_type: type[BaseModelType] = with_content_type

        # If the provided content type model is abstract, create a concrete one.
        if real_content_type.meta.abstract:
            in_admin = real_content_type.meta.in_admin
            no_admin_create = real_content_type.meta.no_admin_create
            meta_args = {
                "tablename": "contenttypes",
                "registry": self,
                "in_admin": True if in_admin is None else in_admin,
                "no_admin_create": True if no_admin_create is None else no_admin_create,
            }

            new_meta: MetaInfo = MetaInfo(None, **meta_args)
            # Model adds itself to registry and executes callbacks.
            real_content_type = create_edgy_model(
                "ContentType",
                with_content_type.__module__,
                __metadata__=new_meta,
                __bases__=(with_content_type,),
            )
        # If the content type model is not abstract but not yet in this registry.
        elif real_content_type.meta.registry is None:
            real_content_type.add_to_registry(self, name="ContentType")
        self.content_type = real_content_type

        def callback(model_class: type[BaseModelType]) -> None:
            """
            Callback function executed when a model is registered. It adds a
            'content_type' field to the model if not already present.
            """
            # Skip ContentType model itself to avoid recursion.
            if issubclass(model_class, ContentType):
                return
            # Skip if field is explicitly set or removed when copying.
            for field in model_class.meta.fields.values():
                if isinstance(field, BaseContentTypeField):
                    if (
                        old_content_type_to_replace is not None
                        and field.target is old_content_type_to_replace
                    ):
                        field.target_registry = self
                        field.target = real_content_type
                        # Simply overwrite the related field in ContentType.
                        real_content_type.meta.fields[field.related_name] = RelatedField(
                            name=field.related_name,
                            foreign_key_name=field.name,
                            related_from=model_class,
                            owner=real_content_type,
                        )
                    return

            # E.g., if the field is explicitly excluded.
            if "content_type" in model_class.meta.fields:
                return

            related_name = f"reverse_{model_class.__name__.lower()}"
            # Ensure no duplicate related name in ContentType.
            assert related_name not in real_content_type.meta.fields, (
                f"duplicate model name: {model_class.__name__}"
            )

            field_args: dict[str, Any] = {
                "name": "content_type",
                "owner": model_class,
                "to": real_content_type,
                "no_constraint": real_content_type.no_constraint,
                "no_copy": True,
            }
            # Set cascade deletion properties if registries differ.
            if model_class.meta.registry is not real_content_type.meta.registry:
                field_args["relation_has_post_delete_callback"] = True
                field_args["force_cascade_deletion_relation"] = True
            # Add the ContentTypeField to the model.
            model_class.meta.fields["content_type"] = ContentTypeField(**field_args)
            # Add the reverse related field to ContentType.
            real_content_type.meta.fields[related_name] = RelatedField(
                name=related_name,
                foreign_key_name="content_type",
                related_from=model_class,
                owner=real_content_type,
            )

        # Register the callback to be executed for all models (not one-time).
        self.register_callback(None, callback, one_time=False)

    @property
    def metadata_by_name(self) -> MetaDataDict:
        """
        Provides a `MetaDataDict` instance, caching it for subsequent access.
        This property is the primary way to access `sqlalchemy.MetaData` objects
        by a given logical name (e.g., 'default', 'extra_db_name').
        """
        # Lazy initialization of _metadata_by_name.
        if getattr(self, "_metadata_by_name", None) is None:
            self._metadata_by_name = MetaDataDict(registry=self)
        return self._metadata_by_name

    @metadata_by_name.setter
    def metadata_by_name(self, value: MetaDataDict) -> None:
        """
        Setter for `metadata_by_name`. Clears the existing metadata and populates
        it with the provided `MetaDataDict` values, then processes `metadata_by_url`.
        """
        metadata_dict = self.metadata_by_name
        metadata_dict.clear()
        for k, v in value.items():
            metadata_dict[k] = v
        self.metadata_by_url.process()

    @property
    def metadata(self) -> sqlalchemy.MetaData:
        """
        Deprecated: Provides access to the default SQLAlchemy MetaData object.
        Use `metadata_by_name` or `metadata_by_url` for more explicit access.
        """
        warnings.warn(
            "metadata is deprecated use metadata_by_name or metadata_by_url instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.metadata_by_name[None]

    def get_model(
        self,
        model_name: str,
        *,
        include_content_type_attr: bool = True,
        exclude: Container[str] = (),
    ) -> type[BaseModelType]:
        """
        Retrieves a registered model by its name.

        Args:
            model_name (str): The name of the model to retrieve.
            include_content_type_attr (bool): If True and `model_name` is
                "ContentType", returns the configured content type model.
                Defaults to True.
            exclude (Container[str]): A collection of registry types (e.g.,
                                      "pattern_models") to exclude from the
                                      search.

        Returns:
            type[BaseModelType]: The found model class.

        Raises:
            LookupError: If no model with the given name is found.
        """
        # Handle special case for ContentType model.
        if (
            include_content_type_attr
            and model_name == "ContentType"
            and self.content_type is not None
        ):
            return self.content_type
        # Search through various model registries.
        for model_dict_name in self.model_registry_types:
            if model_dict_name in exclude:
                continue
            model_dict: dict = getattr(self, model_dict_name)
            if model_name in model_dict:
                return cast(type["BaseModelType"], model_dict[model_name])
        raise LookupError(f'Registry doesn\'t have a "{model_name}" model.') from None

    def delete_model(self, model_name: str) -> bool:
        """
        Deletes a model from the registry by its name.

        Args:
            model_name (str): The name of the model to delete.

        Returns:
            bool: True if the model was found and deleted, False otherwise.
        """
        self.admin_models.discard(model_name)  # Remove from admin models set.
        for model_dict_name in self.model_registry_types:
            model_dict: dict = getattr(self, model_dict_name)
            if model_name in model_dict:
                del model_dict[model_name]  # Delete the model.
                return True
        return False

    def refresh_metadata(
        self,
        *,
        update_only: bool = False,
        multi_schema: bool | re.Pattern | str = False,
        ignore_schema_pattern: re.Pattern | str | None = "information_schema",
    ) -> None:
        """
        Refreshes the SQLAlchemy MetaData objects associated with the models
        in the registry. This is crucial for ensuring that table definitions
        are up-to-date, especially in multi-schema or dynamic reflection scenarios.

        Args:
            update_only (bool): If True, only updates existing table definitions
                                without clearing the metadata first. Defaults to
                                False.
            multi_schema (bool | re.Pattern | str): If True, enables multi-schema
                reflection based on detected schemas. Can also be a regex pattern
                or string to match specific schemas. Defaults to False.
            ignore_schema_pattern (re.Pattern | str | None): A regex pattern
                or string to ignore certain schemas during multi-schema reflection.
                Defaults to "information_schema".
        """
        if not update_only:
            for val in self.metadata_by_name.values():
                val.clear()  # Clear existing metadata if not just updating.

        maindatabase_url = str(self.database.url)
        # Determine schemes to process based on multi_schema setting.
        if multi_schema is not False:
            schemes_tree: dict[str, tuple[str | None, list[str]]] = {
                v[0]: (key, v[2])
                for key, v in run_sync(self.schema.get_schemes_tree(no_reflect=True)).items()
            }
        else:
            schemes_tree = {
                maindatabase_url: (None, [self.db_schema]),
                **{str(v.url): (k, [None]) for k, v in self.extra.items()},
            }

        # Compile regex patterns if provided as strings.
        if isinstance(multi_schema, str):
            multi_schema = re.compile(multi_schema)
        if isinstance(ignore_schema_pattern, str):
            ignore_schema_pattern = re.compile(ignore_schema_pattern)

        # Iterate through all registered models.
        for model_class in self.models.values():
            if not update_only:
                model_class._table = None  # Clear cached table.
                model_class._db_schemas = {}  # Clear cached db schemas.
            url = str(model_class.database.url)
            if url in schemes_tree:
                extra_key, schemes = schemes_tree[url]
                for schema in schemes:
                    if multi_schema is not False:
                        # Skip if multi_schema is enabled but pattern doesn't match.
                        if multi_schema is not True and multi_schema.match(schema) is None:
                            continue
                        # Skip if schema matches ignore pattern.
                        if (
                            ignore_schema_pattern is not None
                            and ignore_schema_pattern.match(schema) is not None
                        ):
                            continue
                        # Handle tenant models and explicit schema usage.
                        if not getattr(model_class.meta, "is_tenant", False):
                            if (
                                model_class.__using_schema__ is Undefined
                                or model_class.__using_schema__ is None
                            ):
                                if schema != "":
                                    continue
                            elif model_class.__using_schema__ != schema:
                                continue
                    # Initialize table schema for the model.
                    model_class.table_schema(schema=schema, metadata=self.metadata_by_url[url])

        # Don't initialize reflected models to keep metadata clean if not updating.
        if not update_only:
            for model_class in self.reflected.values():
                model_class._table = None
                model_class._db_schemas = {}

    def register_callback(
        self,
        name_or_class: type[BaseModelType] | str | None,
        callback: Callable[[type[BaseModelType]], None],
        one_time: bool | None = None,
    ) -> None:
        """
        Registers a callback function to be executed when a model is added
        or a specific model is accessed.

        Args:
            name_or_class (type[BaseModelType] | str | None): The model class,
                model name (string), or None for a general callback applied to
                all models.
            callback (Callable[[type[BaseModelType]], None]): The callback
                                                              function to
                                                              execute. It takes
                                                              the model class
                                                              as an argument.
            one_time (bool | None): If True, the callback will only be executed
                                    once. If None, it defaults to True for
                                    model-specific callbacks and False for
                                    general callbacks.
        """
        if one_time is None:
            # True for model specific callbacks, False for general callbacks.
            one_time = name_or_class is not None
        called: bool = False
        if name_or_class is None:  # General callback for all models.
            for model in self.models.values():
                callback(model)
                called = True
            for model in self.reflected.values():
                callback(model)
                called = True
            for name, model in self.tenant_models.items():
                # For tenant-only models, ensure they are not already in general models.
                if name not in self.models:
                    callback(model)
                    called = True
        elif not isinstance(name_or_class, str):  # Specific model class.
            callback(name_or_class)
            called = True
        else:  # Specific model by name.
            model_class = None
            with contextlib.suppress(LookupError):
                model_class = self.get_model(name_or_class)
            if model_class is not None:
                callback(model_class)
                called = True
        # Convert model class to its name if it was passed as a type.
        if name_or_class is not None and not isinstance(name_or_class, str):
            name_or_class = name_or_class.__name__
        if called and one_time:
            return  # If already called and is one-time, exit.
        if one_time:
            self._onetime_callbacks[name_or_class].append(callback)
        else:
            self._callbacks[name_or_class].append(callback)

    def execute_model_callbacks(self, model_class: type[BaseModelType]) -> None:
        """
        Executes all registered callbacks (one-time and persistent) for a
        given model class.

        Args:
            model_class (type[BaseModelType]): The model class for which to
                                               execute callbacks.
        """
        name = model_class.__name__
        # Execute one-time callbacks specific to this model.
        callbacks = self._onetime_callbacks.get(name)
        while callbacks:
            callbacks.pop()(model_class)

        # Execute general one-time callbacks.
        callbacks = self._onetime_callbacks.get(None)
        while callbacks:
            callbacks.pop()(model_class)

        # Execute persistent callbacks specific to this model.
        callbacks = self._callbacks.get(name)
        if callbacks:
            for callback in callbacks:
                callback(model_class)

        # Execute general persistent callbacks.
        callbacks = self._callbacks.get(None)
        if callbacks:
            for callback in callbacks:
                callback(model_class)

    @cached_property
    def declarative_base(self) -> Any:
        """
        Returns a SQLAlchemy declarative base, either with a specific schema
        or a default one. This is cached for performance.
        """
        if self.db_schema:
            metadata = sqlalchemy.MetaData(schema=self.db_schema)
        else:
            metadata = sqlalchemy.MetaData()
        return sa_declarative_base(metadata=metadata)

    @property
    def engine(self) -> AsyncEngine:
        """
        Returns the asynchronous SQLAlchemy engine for the primary database.
        Requires the database to be connected.

        Raises:
            AssertionError: If the database is not initialized or connected.
        """
        assert self.database.is_connected and self.database.engine, "database not initialized"
        return self.database.engine

    @property
    def sync_engine(self) -> Engine:
        """
        Returns the synchronous SQLAlchemy engine derived from the asynchronous
        engine for the primary database.
        """
        return self.engine.sync_engine

    def init_models(
        self, *, init_column_mappers: bool = True, init_class_attrs: bool = True
    ) -> None:
        """
        Initializes lazy-loaded parts of model metadata (e.g., column mappers
        and class attributes). This method is normally not required to be called
        explicitly as it's handled internally.

        Args:
            init_column_mappers (bool): If True, initializes SQLAlchemy column
                                        mappers. Defaults to True.
            init_class_attrs (bool): If True, initializes model class attributes.
                                     Defaults to True.
        """
        for model_class in self.models.values():
            model_class.meta.full_init(
                init_column_mappers=init_column_mappers, init_class_attrs=init_class_attrs
            )

        for model_class in self.reflected.values():
            model_class.meta.full_init(
                init_column_mappers=init_column_mappers, init_class_attrs=init_class_attrs
            )

    def invalidate_models(self, *, clear_class_attrs: bool = True) -> None:
        """
        Invalidates all lazy-loaded parts of model metadata. They will be
        automatically re-initialized upon next access. This is useful for
        scenarios where model definitions might change dynamically.

        Args:
            clear_class_attrs (bool): If True, clears cached class attributes.
                                      Defaults to True.
        """
        for model_class in self.models.values():
            model_class.meta.invalidate(clear_class_attrs=clear_class_attrs)
        for model_class in self.reflected.values():
            model_class.meta.invalidate(clear_class_attrs=clear_class_attrs)

    def get_tablenames(self) -> set[str]:
        """
        Returns a set of all table names associated with the models registered
        in this registry (including reflected models).
        """
        return_set = set()
        for model_class in self.models.values():
            return_set.add(model_class.meta.tablename)
        for model_class in self.reflected.values():
            return_set.add(model_class.meta.tablename)
        return return_set

    def _automigrate_update(
        self,
        migration_settings: EdgySettings,
    ) -> None:
        """
        Internal synchronous method to run database migrations using Monkay.

        Args:
            migration_settings (EdgySettings): Settings specific to the migration
                                              process.
        """
        from edgy import Instance, monkay
        from edgy.cli.base import upgrade

        self._is_automigrated = True
        with monkay.with_full_overwrite(
            extensions={},
            settings=migration_settings,
            instance=Instance(registry=self),
            evaluate_settings_with={},
            apply_extensions=True,
        ):
            upgrade()

    async def _automigrate(self) -> None:
        """
        Asynchronously triggers database migrations if `automigrate_config`
        is provided and automatic migrations are allowed.
        """
        from edgy import monkay

        migration_settings = self._automigrate_config
        if migration_settings is None or not monkay.settings.allow_automigrations:
            self._is_automigrated = True
            return

        await asyncio.to_thread(self._automigrate_update, migration_settings)

    async def _connect_and_init(self, name: str | None, database: Database) -> None:
        """
        Internal asynchronous method to connect to a database and initialize
        models, including automatic reflection of pattern models.

        Args:
            name (str | None): The name of the database (None for the default).
            database (Database): The database instance to connect to.

        Raises:
            BaseException: If an error occurs during database connection or
                           model initialization, it re-raises the exception
                           after attempting to disconnect.
        """
        from edgy.core.db.models.metaclasses import MetaInfo

        await database.connect()
        if not self._is_automigrated:
            await self._automigrate()
        if not self.pattern_models or name in self.dbs_reflected:
            return  # No pattern models to reflect or already reflected.

        schemes: set[None | str] = set()
        for pattern_model in self.pattern_models.values():
            if name not in pattern_model.meta.databases:
                continue
            schemes.update(pattern_model.meta.schemes)

        tmp_metadata = sqlalchemy.MetaData()
        for schema in schemes:
            await database.run_sync(tmp_metadata.reflect, schema=schema)

        try:
            for table in tmp_metadata.tables.values():
                for pattern_model in self.pattern_models.values():
                    if name not in pattern_model.meta.databases or table.schema not in schemes:
                        continue
                    assert pattern_model.meta.model is pattern_model
                    # table.key would contain the schema name
                    if not pattern_model.meta.include_pattern.match(table.name) or (
                        pattern_model.meta.exclude_pattern
                        and pattern_model.meta.exclude_pattern.match(table.name)
                    ):
                        continue
                    if pattern_model.fields_not_supported_by_table(table):  # type: ignore
                        continue

                    new_name = pattern_model.meta.template(table)
                    old_model: type[BaseModelType] | None = None
                    with contextlib.suppress(LookupError):
                        old_model = self.get_model(
                            new_name, include_content_type_attr=False, exclude=("pattern_models",)
                        )
                    if old_model is not None:
                        raise Exception(
                            f"Conflicting model: {old_model.__name__} with pattern model: "
                            f"{pattern_model.__name__}"
                        )
                    # Create a concrete model from the pattern model.
                    concrete_reflect_model = pattern_model.copy_edgy_model(
                        name=new_name, meta_info_class=MetaInfo
                    )
                    concrete_reflect_model.meta.no_copy = True
                    concrete_reflect_model.meta.tablename = table.name
                    concrete_reflect_model.__using_schema__ = table.schema
                    concrete_reflect_model.add_to_registry(self, database=database)

            self.dbs_reflected.add(name)  # Mark this database as reflected.
        except BaseException as exc:
            await database.disconnect()  # Ensure disconnection on error.
            raise exc

    async def __aenter__(self) -> Registry:
        """
        Asynchronously connects to all registered databases (primary and extra)
        and initializes models. This method is designed to be used with `async with`.
        """
        dbs: list[tuple[str | None, Database]] = [(None, self.database)]
        for name, db in self.extra.items():
            dbs.append((name, db))
        # Initiate connection and initialization for all databases concurrently.
        ops = [self._connect_and_init(name, db) for name, db in dbs]
        results: list[BaseException | bool] = await asyncio.gather(*ops, return_exceptions=True)

        # Handle any connection failures.
        if any(isinstance(x, BaseException) for x in results):
            ops2 = []
            for num, value in enumerate(results):
                if not isinstance(value, BaseException):
                    # Disconnect successfully connected databases if others failed.
                    ops2.append(dbs[num][1].disconnect())
                else:
                    logger.opt(exception=value).error("Failed to connect database.")
            await asyncio.gather(*ops2)  # Await disconnections.
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None,
    ) -> None:
        """
        Asynchronously disconnects from all registered databases (primary and extra).
        This method is designed to be used with `async with`.
        """
        ops = [self.database.disconnect()]
        for value in self.extra.values():
            ops.append(value.disconnect())
        await asyncio.gather(*ops)  # Await all disconnections concurrently.

    @contextlib.contextmanager
    def with_async_env(
        self, loop: asyncio.AbstractEventLoop | None = None
    ) -> Generator[Registry, None, None]:
        """
        Provides a synchronous context manager for asynchronous operations,
        managing the event loop and registry lifecycle (`__aenter__` and
        `__aexit__`). This is useful for integrating asynchronous Edgy
        operations into synchronous contexts.

        Args:
            loop (asyncio.AbstractEventLoop | None): An optional event loop
                                                    to use. If None, it tries
                                                    to get the running loop
                                                    or creates a new one.

        Yields:
            Registry: The connected Registry instance.
        """
        close: bool = False
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
                # When in async context, we don't create a new loop.
            except RuntimeError:
                # Also when called recursively and current_eventloop is available.
                loop = current_eventloop.get()
                if loop is None:
                    loop = asyncio.new_event_loop()
                    close = True  # Mark for closing if a new loop was created.

        token = current_eventloop.set(loop)  # Set the current event loop.
        try:
            # Enter the async context of the registry.
            yield run_sync(self.__aenter__(), loop=loop)
        finally:
            run_sync(self.__aexit__(), loop=loop)  # Exit the async context.
            current_eventloop.reset(token)  # Reset the current event loop.
            if close:
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()  # Close the event loop if it was created here.

    @overload
    def asgi(
        self,
        app: None,
        handle_lifespan: bool = False,
    ) -> Callable[[ASGIApp], ASGIHelper]: ...

    @overload
    def asgi(
        self,
        app: ASGIApp,
        handle_lifespan: bool = False,
    ) -> ASGIHelper: ...

    def asgi(
        self,
        app: ASGIApp | None = None,
        handle_lifespan: bool = False,
    ) -> ASGIHelper | Callable[[ASGIApp], ASGIHelper]:
        """
        Returns an ASGI wrapper for the registry, allowing it to integrate
        with ASGI applications and manage database lifespan events.

        Args:
            app (ASGIApp | None): The ASGI application to wrap. If None, returns
                                  a partial function that expects an ASGIApp.
            handle_lifespan (bool): If True, the ASGIHelper will fully manage
                                    the ASGI 'lifespan' scope, including sending
                                    'startup.complete' and 'shutdown.complete'
                                    messages. Defaults to False.

        Returns:
            ASGIHelper | Callable[[ASGIApp], ASGIHelper]: An ASGIHelper instance
                                                          or a partial function
                                                          to create one.
        """
        if app is not None:
            return ASGIHelper(app=app, registry=self, handle_lifespan=handle_lifespan)
        return partial(ASGIHelper, registry=self, handle_lifespan=handle_lifespan)

    async def create_all(
        self, refresh_metadata: bool = True, databases: Sequence[str | None] = (None,)
    ) -> None:
        """
        Asynchronously creates all database tables for the registered models.
        This includes creating schemas if `db_schema` is set.

        Args:
            refresh_metadata (bool): If True, refreshes the metadata before
                                     creating tables to ensure definitions are
                                     up-to-date. Defaults to True.
            databases (Sequence[str | None]): A sequence of database names (or
                                             None for the default database) for
                                             which to create tables. Defaults
                                             to (None,).
        """
        # Refresh metadata to avoid old references to non-existing tables/fks.
        if refresh_metadata:
            self.refresh_metadata(multi_schema=True)
        if self.db_schema:
            await self.schema.create_schema(
                self.db_schema, True, True, update_cache=True, databases=databases
            )
        else:
            # Fallback for databases that don't support schemas.
            for database in databases:
                db = self.database if database is None else self.extra[database]
                async with db as db:
                    with db.force_rollback(False):  # Disable rollback for DDL.
                        await db.create_all(self.metadata_by_name[database])

    async def drop_all(self, databases: Sequence[str | None] = (None,)) -> None:
        """
        Asynchronously drops all database tables for the registered models.
        This includes dropping schemas if `db_schema` is set.

        Args:
            databases (Sequence[str | None]): A sequence of database names (or
                                             None for the default database) for
                                             which to drop tables. Defaults to
                                             (None,).
        """
        if self.db_schema:
            await self.schema.drop_schema(
                self.db_schema, cascade=True, if_exists=True, databases=databases
            )
        else:
            # Fallback for databases that don't support schemas.
            for database_name in databases:
                db = self.database if database_name is None else self.extra[database_name]
                async with db as db:
                    with db.force_rollback(False):  # Disable rollback for DDL.
                        await db.drop_all(self.metadata_by_name[database_name])


__all__ = ["Registry"]
