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
            return cast(QuerySet, self.filter(and_()))
        UserField = self.owner.meta.fields["users"]
        GroupField = self.owner.meta.fields.get("groups", None)
        query = cast(QuerySet, self.all())
        for source in sources:
            if isinstance(source, UserField.target):
                clause: dict[str, Any] = {"users__pk": source.pk}
                if GroupField is not None:
                    clause[f"groups__{self.owner.users_field_group}__pk"] = source.pk
                query = query.or_(**clause)
                return query
            elif GroupField is not None and isinstance(source, GroupField.target):
                query = query.or_(groups__pk=source.pk)
            else:
                raise ValueError(f"Invalid source: {source}.")
        return query

    def users(
        self,
        permissions: Sequence[str] | str,
        model_names: Sequence[str] | str | None = None,
        objects: Sequence[BaseModelType] | BaseModelType | None = None,
    ) -> QuerySet:
        if isinstance(permissions, str):
            permissions = [permissions]
        if isinstance(model_names, str):
            model_names = [model_names]
        if isinstance(objects, BaseModelType):
            objects = [objects]
        UserField = self.owner.meta.fields["users"]
        GroupField = self.owner.meta.fields.get("groups", None)
        if objects is not None and len(objects) == 0:
            # none
            return cast("QuerySet", UserField.target.query.filter(and_()))
        clauses: dict[str, Any] = {f"{UserField.reverse_name}__name__in": permissions}
        if model_names is not None:
            clauses[f"{UserField.reverse_name}__model_name__in"] = model_names
        if GroupField is not None:
            clauses[f"{self.owner.groups_field_user}__{GroupField.reverse_name}__name__in"] = (
                permissions
            )
            if model_names is not None:
                clauses[
                    f"{self.owner.groups_field_user}__{GroupField.reverse_name}__model_name__in"
                ] = model_names
        query = cast("QuerySet", UserField.target.query.filter(**clauses))
        if objects is not None:
            for obj in objects:
                clause = {f"{UserField.reverse_name}__obj__pk": obj.pk}
                if GroupField is not None:
                    clause[
                        f"{self.owner.groups_field_user}__{GroupField.reverse_name}__obj__pk"
                    ] = obj.pk
                query = query.or_(**clause)
        return query

    def groups(
        self,
        permissions: Sequence[str] | str,
        model_names: Sequence[str] | str | None = None,
        objects: Sequence[BaseModelType] | BaseModelType | None = None,
    ) -> QuerySet:
        if isinstance(permissions, str):
            permissions = [permissions]
        if isinstance(model_names, str):
            model_names = [model_names]
        if isinstance(objects, BaseModelType):
            objects = [objects]
        GroupField = self.owner.meta.fields["groups"]
        if objects is not None and len(objects) == 0:
            # none
            return cast("QuerySet", GroupField.target.query.filter(and_()))
        clauses: dict[str, Any] = {f"{GroupField.reverse_name}__name__in": permissions}
        if model_names is not None:
            clauses[f"{GroupField.reverse_name}__model_name__in"] = model_names
        query = cast("QuerySet", GroupField.target.query.filter(**clauses))
        if objects is not None:
            for obj in objects:
                clause = {f"{GroupField.reverse_name}__obj__pk": obj.pk}
                query = query.or_(**clause)
        return query
