from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from edgy.core.db.models.managers import Manager
from edgy.core.db.models.types import BaseModelType
from edgy.core.db.querysets.clauses import and_

if TYPE_CHECKING:
    from edgy.core.db.querysets.base import QuerySet


class PermissionManager(Manager):
    def permissions_of(self, sources: Sequence[BaseModelType] | BaseModelType) -> QuerySet:
        if isinstance(sources, BaseModelType):
            sources = [sources]
        if len(sources) == 0:
            # none
            return cast("QuerySet", self.filter(and_()))
        UserField = self.owner.meta.fields["users"]
        assert (
            UserField.embed_through is False or UserField.embed_through
        ), "users field need embed_through=foo|False."
        GroupField = self.owner.meta.fields.get("groups", None)
        assert (
            GroupField is None or GroupField.embed_through is False or GroupField.embed_through
        ), "groups field need embed_through=foo|False."

        clauses: list[dict[str, Any]] = []
        for source in sources:
            if isinstance(source, UserField.target):
                clauses.append({"users__pk": source})
                if GroupField is not None:
                    clauses.append({f"groups__{self.owner.users_field_group}__pk": source})
            elif GroupField is not None and isinstance(source, GroupField.target):
                clauses.append({"groups__pk": source})
            else:
                raise ValueError(f"Invalid source: {source}.")
        return cast("QuerySet", self.or_(*clauses))

    def users(
        self,
        permissions: Sequence[str] | str,
        model_names: Sequence[str | None] | str | None = None,
        objects: Sequence[BaseModelType | None] | BaseModelType | None = None,
        include_null_model_name: bool = True,
        include_null_object: bool = True,
    ) -> QuerySet:
        if isinstance(permissions, str):
            permissions = [permissions]
        if isinstance(model_names, str):
            model_names = [model_names]
        if model_names is not None and include_null_model_name:
            model_names = [*model_names, None]
        if isinstance(objects, BaseModelType):
            objects = [objects]
        if objects is not None and include_null_object:
            objects = [*objects, None]
        UserField = self.owner.meta.fields["users"]
        assert (
            UserField.embed_through is False or UserField.embed_through
        ), "users field need embed_through=foo|False."
        GroupField = self.owner.meta.fields.get("groups", None)
        assert (
            GroupField is None or GroupField.embed_through is False or GroupField.embed_through
        ), "groups field need embed_through=foo|False."
        assert (
            GroupField is None
            or GroupField.target.meta.fields[self.owner.users_field_group].embed_through is False
            or GroupField.target.meta.fields[self.owner.users_field_group].embed_through
        ), f"{GroupField.target} {self.owner.users_field_group} field need embed_through=foo|False."
        ModelNameField = self.owner.meta.fields.get("name_model", None)
        ContentTypeField = self.owner.meta.fields.get("obj", None)
        if objects is not None and len(objects) == 0:
            # none
            return cast("QuerySet", UserField.target.query.filter(and_()))
        clauses: list[dict[str, Any]] = [{f"{UserField.reverse_name}__name__in": permissions}]
        if model_names is not None:
            if ModelNameField is not None:
                clauses[-1][f"{UserField.reverse_name}__name_model__in"] = model_names
            elif ContentTypeField is not None:
                clauses[-1][f"{UserField.reverse_name}__obj__name__in"] = model_names

        if GroupField is not None:
            clauses.append({})
            groups_field_user = GroupField.target.meta.fields[
                self.owner.users_field_group
            ].reverse_name
            assert isinstance(
                groups_field_user, str
            ), f"{GroupField.target} {self.owner.users_field_group} field needs reverse_name."
            clauses[-1][f"{groups_field_user}__{GroupField.reverse_name}__name__in"] = permissions
            if model_names is not None:
                if ModelNameField is not None:
                    clauses[-1][
                        f"{groups_field_user}__{GroupField.reverse_name}__name_model__in"
                    ] = model_names
                elif ContentTypeField is not None:
                    clauses[-1][
                        f"{groups_field_user}__{GroupField.reverse_name}__obj__name__in"
                    ] = model_names

        query = cast("QuerySet", UserField.target.query.or_(*clauses))

        if objects is not None:
            obj_clauses = []
            for obj in objects:
                obj_clauses.append({f"{UserField.reverse_name}__obj": obj})
                if GroupField is not None:
                    obj_clauses[-1][
                        f"{self.owner.groups_field_user}__{GroupField.reverse_name}__obj"
                    ] = obj
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
        if isinstance(permissions, str):
            permissions = [permissions]
        if isinstance(model_names, str):
            model_names = [model_names]
        if model_names is not None and include_null_model_name:
            model_names = [*model_names, None]
        if isinstance(objects, BaseModelType):
            objects = [objects]
        if objects is not None and include_null_object:
            objects = [*objects, None]
        GroupField = self.owner.meta.fields["groups"]
        assert (
            GroupField.embed_through is False or GroupField.embed_through
        ), "groups field need embed_through=foo|False."
        assert (
            GroupField.target.meta.fields[self.owner.users_field_group].embed_through is False
            or GroupField.target.meta.fields[self.owner.users_field_group].embed_through
        ), f"{GroupField.target} {self.owner.users_field_group} field need embed_through=foo|False."
        ModelNameField = self.owner.meta.fields.get("name_model", None)
        ContentTypeField = self.owner.meta.fields.get("obj", None)
        if objects is not None and len(objects) == 0:
            # none
            return cast("QuerySet", GroupField.target.query.filter(and_()))
        clauses: dict[str, Any] = {f"{GroupField.reverse_name}__name__in": permissions}
        if model_names is not None:
            if ModelNameField is not None:
                clauses[f"{GroupField.reverse_name}__name_model__in"] = model_names
            elif ContentTypeField is not None:
                clauses[f"{GroupField.reverse_name}__obj__name__in"] = model_names
        query = cast("QuerySet", GroupField.target.query.filter(**clauses))
        if objects is not None:
            for obj in objects:
                clause = {f"{GroupField.reverse_name}__obj": obj}
                query = query.or_(**clause)
        return query
