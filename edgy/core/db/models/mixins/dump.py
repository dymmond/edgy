from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

import orjson
from pydantic import BaseModel

from edgy.core.db.context_vars import (
    MODEL_GETATTR_BEHAVIOR,
)

if TYPE_CHECKING:
    from edgy.core.db.models.metaclasses import MetaInfo

_empty = cast(set[str], frozenset())


class DumpMixin:
    """
    Dump mixin.
    """

    meta: ClassVar[MetaInfo]

    def model_dump(self: BaseModel, show_pk: bool | None = None, **kwargs: Any) -> dict[str, Any]:
        """
        An updated version of the model dump.
        It can show the pk always and handles the exclude attribute on fields correctly and
        contains the custom logic for fields with getters

        Extra Args:
            show_pk: bool - Enforces showing the primary key in the model_dump.
        """
        meta = self.meta
        # we want a copy
        _exclude: set[str] | dict[str, Any] | None = kwargs.pop("exclude", None)
        if _exclude is None:
            initial_full_field_exclude: set[str] = _empty
            # must be a writable dict
            exclude_passed: dict[str, Any] = {}
            exclude_second_pass: dict[str, Any] = {}
        elif isinstance(_exclude, dict):
            initial_full_field_exclude = {k for k, v in _exclude.items() if v is True}
            exclude_passed = copy.copy(_exclude)
            exclude_second_pass = _exclude
        else:
            initial_full_field_exclude = set(_exclude)
            exclude_passed = dict.fromkeys(initial_full_field_exclude, True)
            exclude_second_pass = exclude_passed.copy()

        need_second_pass: set[str] = set()
        for field_name in meta.special_getter_fields:
            exclude_passed[field_name] = True
            if (
                field_name not in initial_full_field_exclude
                and not meta.fields[field_name].exclude
            ):
                need_second_pass.add(field_name)
        for field_name in meta.foreign_key_fields:
            field = meta.fields[field_name]
            # when excluded we don't need to consider to add a second pass.
            if field_name in initial_full_field_exclude or field.exclude:
                continue
            if field.target.meta.needs_special_serialization:
                exclude_passed[field_name] = True
                need_second_pass.add(field_name)
        include: set[str] | dict[str, Any] | None = kwargs.pop("include", None)
        mode: Literal["json", "python"] = kwargs.pop("mode", "python")

        should_show_pk = self.__show_pk__ if show_pk is None else show_pk
        result_dict: dict[str, Any] = super().model_dump(
            exclude=exclude_passed, include=include, mode=mode, **kwargs
        )
        token = MODEL_GETATTR_BEHAVIOR.set("passdown")
        try:
            for field_name in need_second_pass:
                # include or pkname (if should_show_pk)
                if not (
                    (should_show_pk and field_name in self.pknames)
                    or include is None
                    or field_name in include
                ):
                    continue
                field = meta.fields[field_name]
                try:
                    retval = getattr(self, field_name)
                except AttributeError:
                    continue
                sub_include = None
                if isinstance(include, dict):
                    sub_include = include.get(field_name, None)
                    if sub_include is True:
                        sub_include = None
                sub_exclude = exclude_second_pass.get(field_name, None)
                assert sub_exclude is not True, "field should have been excluded"
                # for e.g. CompositeFields which generate via __get__
                if isinstance(retval, BaseModel):
                    retval = retval.model_dump(
                        include=sub_include, exclude=sub_exclude, mode=mode, **kwargs
                    )
                else:
                    assert sub_include is None, "sub include filters for no pydantic model"
                    assert sub_exclude is None, "sub exclude filters for no pydantic model"
                    if mode == "json" and not getattr(field, "unsafe_json_serialization", False):
                        # skip field if it isn't a BaseModel and the mode is json and
                        # unsafe_json_serialization is not set
                        # currently unsafe_json_serialization exists only on CompositeFields
                        continue
                alias: str = field_name
                if getattr(field, "serialization_alias", None):
                    alias = cast(str, field.serialization_alias)
                elif getattr(field, "alias", None):
                    alias = field.alias
                result_dict[alias] = retval
        finally:
            MODEL_GETATTR_BEHAVIOR.reset(token)
        return result_dict

    def model_dump_json(self, **kwargs: Any) -> str:
        return orjson.dumps(self.model_dump(mode="json", **kwargs)).decode()
