from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from edgy.core.db.models.managers import Manager
from edgy.core.db.models.types import BaseModelType
from edgy.core.db.querysets.clauses import and_

if TYPE_CHECKING:
    from edgy.core.db.querysets.base import QuerySet


class PermissionManager(Manager):
    """
    A custom manager for handling permissions queries within Edgy models.

    This manager provides methods to query permissions based on users, groups,
    models, and specific objects, streamlining access control logic.
    """

    def permissions_of(self, sources: Sequence[BaseModelType] | BaseModelType) -> QuerySet:
        """
        Retrieves permissions associated with specific user or group sources.

        This method queries for permissions linked to the provided user or group
        instances, handling cases where permissions are associated directly
        with users or indirectly through groups.

        Args:
            sources (Sequence[BaseModelType] | BaseModelType): A single
                `BaseModelType` instance (e.g., a User or Group model instance)
                or a sequence of such instances, for which to retrieve permissions.

        Returns:
            QuerySet: A `QuerySet` containing the permissions associated with the
            given sources. If no sources are provided, an empty `QuerySet` is returned.

        Raises:
            ValueError: If an invalid source type is provided that is neither
                a User nor a Group instance (based on the model's field definitions).
            AssertionError: If the 'users' or 'groups' fields on the owner model
                are not configured correctly with `embed_through`.
        """
        if isinstance(sources, BaseModelType):
            sources = [sources]
        if len(sources) == 0:
            # If no sources are provided, return an empty queryset
            return cast("QuerySet", self.filter(and_()))

        # Access the 'users' field definition from the owner model's metadata.
        UserField = self.owner.meta.fields["users"]
        # Ensure the 'users' field has 'embed_through' properly configured.
        assert UserField.embed_through is False or UserField.embed_through, (
            "users field need embed_through=foo|False."
        )

        # Access the 'groups' field definition if it exists.
        GroupField = self.owner.meta.fields.get("groups", None)
        # If 'groups' field exists, ensure it has 'embed_through' properly configured.
        assert (
            GroupField is None or GroupField.embed_through is False or GroupField.embed_through
        ), "groups field need embed_through=foo|False."

        clauses: list[dict[str, Any]] = []
        for source in sources:
            # Check if the source is an instance of the UserField's target model.
            if isinstance(source, UserField.target):
                # Add a clause to filter by the user's primary key.
                clauses.append({"users__pk": source})
                # If a 'groups' field exists, also include permissions via user's groups.
                if GroupField is not None:
                    # Construct a clause to filter permissions related to the user's groups.
                    clauses.append({f"groups__{self.owner.users_field_group}__pk": source})
            # Check if the source is an instance of the GroupField's target model (if GroupField exists).
            elif GroupField is not None and isinstance(source, GroupField.target):
                # Add a clause to filter by the group's primary key.
                clauses.append({"groups__pk": source})
            else:
                # Raise an error for invalid source types.
                raise ValueError(f"Invalid source: {source}.")
        # Combine all clauses with an OR condition and return the queryset.
        return cast("QuerySet", self.or_(*clauses))

    def users(
        self,
        permissions: Sequence[str] | str,
        model_names: Sequence[str | None] | str | None = None,
        objects: Sequence[BaseModelType | None] | BaseModelType | None = None,
        include_null_model_name: bool = True,
        include_null_object: bool = True,
    ) -> QuerySet:
        """
        Retrieves users who have specified permissions.

        This method allows filtering users based on their direct permissions,
        permissions inherited through groups, and permissions tied to specific
        model names or objects.

        Args:
            permissions (Sequence[str] | str): A single permission string or a
                sequence of permission strings (e.g., "can_edit", "can_delete").
            model_names (Sequence[str | None] | str | None, optional): A single
                model name string or a sequence of model names for which the
                permissions apply. `None` can be included to match permissions
                not tied to a specific model. Defaults to `None`.
            objects (Sequence[BaseModelType | None] | BaseModelType | None, optional):
                A single `BaseModelType` instance or a sequence of instances
                for which the permissions apply. `None` can be included to match
                permissions not tied to a specific object. Defaults to `None`.
            include_null_model_name (bool, optional): If `True` and `model_names`
                is provided, `None` will be implicitly added to `model_names`
                to include permissions without a specific model name. Defaults to `True`.
            include_null_object (bool, optional): If `True` and `objects`
                is provided, `None` will be implicitly added to `objects`
                to include permissions without a specific object. Defaults to `True`.

        Returns:
            QuerySet: A `QuerySet` containing user instances that possess the
            specified permissions.

        Raises:
            AssertionError: If the 'users' or 'groups' fields, or the
                `users_field_group` on the group model, are not configured
                correctly with `embed_through` or `reverse_name`.
        """
        # Ensure permissions is a list.
        if isinstance(permissions, str):
            permissions = [permissions]
        # Ensure model_names is a list.
        if isinstance(model_names, str):
            model_names = [model_names]
        # Add None to model_names if required.
        if model_names is not None and include_null_model_name:
            model_names = [*model_names, None]
        # Ensure objects is a list.
        if isinstance(objects, BaseModelType):
            objects = [objects]
        # Add None to objects if required.
        if objects is not None and include_null_object:
            objects = [*objects, None]

        # Get the 'users' field from the owner model's metadata.
        UserField = self.owner.meta.fields["users"]
        # Assert that 'users' field is correctly configured with `embed_through`.
        assert UserField.embed_through is False or UserField.embed_through, (
            "users field need embed_through=foo|False."
        )

        # Get the 'groups' field if it exists.
        GroupField = self.owner.meta.fields.get("groups", None)
        # Assert that 'groups' field (if exists) is correctly configured with `embed_through`.
        assert (
            GroupField is None or GroupField.embed_through is False or GroupField.embed_through
        ), "groups field need embed_through=foo|False."

        # If GroupField exists, assert that the user field within the group's target model
        # (specified by self.owner.users_field_group) is also correctly configured with `embed_through`.
        assert (
            GroupField is None
            or GroupField.target.meta.fields[self.owner.users_field_group].embed_through is False
            or GroupField.target.meta.fields[self.owner.users_field_group].embed_through
        ), (
            f"{GroupField.target} {self.owner.users_field_group} field need embed_through=foo|False."
        )

        # Get the 'name_model' and 'obj' (ContentType) fields if they exist.
        ModelNameField = self.owner.meta.fields.get("name_model", None)
        ContentTypeField = self.owner.meta.fields.get("obj", None)

        # If objects are specified but the list is empty, return an empty queryset for users.
        if objects is not None and len(objects) == 0:
            # none
            return cast("QuerySet", UserField.target.query.filter(and_()))

        # Initialize clauses for direct user permissions.
        clauses: list[dict[str, Any]] = [{f"{UserField.reverse_name}__name__in": permissions}]

        # If model_names are specified, add them to the clause for direct user permissions.
        if model_names is not None:
            if ModelNameField is not None:
                clauses[-1][f"{UserField.reverse_name}__name_model__in"] = model_names
            elif ContentTypeField is not None:
                clauses[-1][f"{UserField.reverse_name}__obj__name__in"] = model_names

        # If a 'groups' field exists, add clauses for permissions inherited through groups.
        if GroupField is not None:
            clauses.append({})  # Add a new dictionary for group-related clauses.
            # Get the reverse name of the user field within the group's target model.
            groups_field_user = GroupField.target.meta.fields[
                self.owner.users_field_group
            ].reverse_name
            # Assert that the reverse name is a string.
            assert isinstance(groups_field_user, str), (
                f"{GroupField.target} {self.owner.users_field_group} field needs reverse_name."
            )
            # Add permission filter for users through groups.
            clauses[-1][f"{groups_field_user}__{GroupField.reverse_name}__name__in"] = permissions
            # If model_names are specified, add them to the group-related clause.
            if model_names is not None:
                if ModelNameField is not None:
                    clauses[-1][
                        f"{groups_field_user}__{GroupField.reverse_name}__name_model__in"
                    ] = model_names
                elif ContentTypeField is not None:
                    clauses[-1][
                        f"{groups_field_user}__{GroupField.reverse_name}__obj__name__in"
                    ] = model_names

        # Combine all clauses (direct user permissions and group-inherited permissions)
        # with an OR condition to build the initial queryset for users.
        query = cast("QuerySet", UserField.target.query.or_(*clauses))

        # If objects are specified, add additional OR clauses to filter by object.
        if objects is not None:
            obj_clauses = []
            for obj in objects:
                # Add clause for direct object permissions.
                obj_clauses.append({f"{UserField.reverse_name}__obj": obj})
                # If GroupField exists, add clause for object permissions through groups.
                if GroupField is not None:
                    obj_clauses[-1][
                        f"{self.owner.groups_field_user}__{GroupField.reverse_name}__obj"
                    ] = obj
            # Combine the existing query with the object-specific clauses using OR.
            query = query.or_(*obj_clauses)
        return query

    def groups(
        self,
        permissions: Sequence[str] | str,
        model_names: Sequence[str | None] | str | None = None,
        objects: Sequence[BaseModelType | None] | BaseModelType | None = None,
        include_null_model_name: bool = True,
        include_null_object: bool = True,
    ) -> QuerySet:
        """
        Retrieves groups that have specified permissions.

        This method allows filtering groups based on their direct permissions
        and permissions tied to specific model names or objects.

        Args:
            permissions (Sequence[str] | str): A single permission string or a
                sequence of permission strings (e.g., "can_edit", "can_delete").
            model_names (Sequence[str | None] | str | None, optional): A single
                model name string or a sequence of model names for which the
                permissions apply. `None` can be included to match permissions
                not tied to a specific model. Defaults to `None`.
            objects (Sequence[BaseModelType | None] | BaseModelType | None, optional):
                A single `BaseModelType` instance or a sequence of instances
                for which the permissions apply. `None` can be included to match
                permissions not tied to a specific object. Defaults to `None`.
            include_null_model_name (bool, optional): If `True` and `model_names`
                is provided, `None` will be implicitly added to `model_names`
                to include permissions without a specific model name. Defaults to `True`.
            include_null_object (bool, optional): If `True` and `objects`
                is provided, `None` will be implicitly added to `objects`
                to include permissions without a specific object. Defaults to `True`.

        Returns:
            QuerySet: A `QuerySet` containing group instances that possess the
            specified permissions.

        Raises:
            AssertionError: If the 'groups' field or the
                `users_field_group` on the group model are not configured
                correctly with `embed_through` or `reverse_name`.
        """
        # Ensure permissions is a list.
        if isinstance(permissions, str):
            permissions = [permissions]
        # Ensure model_names is a list.
        if isinstance(model_names, str):
            model_names = [model_names]
        # Add None to model_names if required.
        if model_names is not None and include_null_model_name:
            model_names = [*model_names, None]
        # Ensure objects is a list.
        if isinstance(objects, BaseModelType):
            objects = [objects]
        # Add None to objects if required.
        if objects is not None and include_null_object:
            objects = [*objects, None]

        # Get the 'groups' field from the owner model's metadata.
        GroupField = self.owner.meta.fields["groups"]
        # Assert that 'groups' field is correctly configured with `embed_through`.
        assert GroupField.embed_through is False or GroupField.embed_through, (
            "groups field need embed_through=foo|False."
        )

        # Assert that the user field within the group's target model
        # (specified by self.owner.users_field_group) is correctly configured with `embed_through`.
        assert (
            GroupField.target.meta.fields[self.owner.users_field_group].embed_through is False
            or GroupField.target.meta.fields[self.owner.users_field_group].embed_through
        ), (
            f"{GroupField.target} {self.owner.users_field_group} field need embed_through=foo|False."
        )

        # Get the 'name_model' and 'obj' (ContentType) fields if they exist.
        ModelNameField = self.owner.meta.fields.get("name_model", None)
        ContentTypeField = self.owner.meta.fields.get("obj", None)

        # If objects are specified but the list is empty, return an empty queryset for groups.
        if objects is not None and len(objects) == 0:
            # none
            return cast("QuerySet", GroupField.target.query.filter(and_()))

        # Initialize clauses for direct group permissions.
        clauses: dict[str, Any] = {f"{GroupField.reverse_name}__name__in": permissions}

        # If model_names are specified, add them to the clause for direct group permissions.
        if model_names is not None:
            if ModelNameField is not None:
                clauses[f"{GroupField.reverse_name}__name_model__in"] = model_names
            elif ContentTypeField is not None:
                clauses[f"{GroupField.reverse_name}__obj__name__in"] = model_names

        # Build the initial queryset for groups by filtering directly on the clauses.
        query = cast("QuerySet", GroupField.target.query.filter(**clauses))

        # If objects are specified, add additional OR clauses to filter by object.
        if objects is not None:
            for obj in objects:
                # Add clause for object permissions.
                clause = {f"{GroupField.reverse_name}__obj": obj}
                # Combine the existing query with the object-specific clause using OR.
                query = query.or_(**clause)
        return query
