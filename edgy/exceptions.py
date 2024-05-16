import typing


class EdgyException(Exception):
    def __init__(
        self,
        *args: typing.Any,
        detail: str = "",
    ):
        self.detail = detail
        super().__init__(*(str(arg) for arg in args if arg), self.detail)

    def __repr__(self) -> str:
        if self.detail:
            return f"{self.__class__.__name__} - {self.detail}"
        return self.__class__.__name__

    def __str__(self) -> str:
        return "".join(self.args).strip()


class FieldDefinitionError(EdgyException): ...


class MarshallFieldDefinitionError(FieldDefinitionError): ...


class ObjectNotFound(EdgyException): ...


class MultipleObjectsReturned(EdgyException): ...


class ImproperlyConfigured(EdgyException): ...


class ForeignKeyBadConfigured(EdgyException): ...


class RelationshipIncompatible(EdgyException): ...


class DuplicateRecordError(EdgyException): ...


class RelationshipNotFound(EdgyException): ...


class QuerySetError(EdgyException): ...


class ModelReferenceError(EdgyException): ...


class SchemaError(EdgyException): ...


class SignalError(EdgyException): ...


class CommandEnvironmentError(EdgyException): ...
