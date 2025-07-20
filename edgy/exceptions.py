import typing


class EdgyException(Exception):
    """
    Base exception class for all Edgy-related errors.

    This class provides a standardized way to handle exceptions within the Edgy
    framework, allowing for a detailed message to be associated with the
    exception.
    """

    def __init__(
        self,
        *args: typing.Any,
        detail: str = "",
    ):
        """
        Initializes the EdgyException.

        Args:
            *args (typing.Any): Variable length argument list to be included
                in the exception message.
            detail (str, optional): A more detailed explanation of the exception.
                Defaults to an empty string.
        """
        self.detail = detail
        # Call the base Exception constructor with string representations of args
        # and the detail message.
        super().__init__(*(str(arg) for arg in args if arg), self.detail)

    def __repr__(self) -> str:
        """
        Returns a string representation of the EdgyException for
        reproduction purposes.

        If a detail message is present, it will be included in the
        representation.
        """
        if self.detail:
            return f"{type(self).__name__} - {self.detail}"
        return type(self).__name__

    def __str__(self) -> str:
        """
        Returns a human-readable string representation of the EdgyException.

        This method concatenates all arguments passed to the exception,
        removing any leading or trailing whitespace.
        """
        return "".join(self.args).strip()


class TableBuildError(EdgyException):
    """
    Exception raised when there is an error during the building of a database table.

    This typically occurs due to issues in model definition or database schema
    synchronization.
    """


class FileOperationError(EdgyException):
    """
    Exception raised when an error occurs during a file operation.

    This can include issues with reading, writing, or manipulating files
    within the Edgy framework, particularly concerning storage backends.
    """


class FieldDefinitionError(EdgyException):
    """
    Exception raised when there is an error in the definition of a model field.

    This indicates issues with the type, constraints, or configuration of
    individual fields within an Edgy model.
    """


class MarshallFieldDefinitionError(FieldDefinitionError):
    """
    Exception raised for errors specific to the definition of a marshall field.

    This extends `FieldDefinitionError` for issues encountered when defining
    fields used in data serialization or deserialization (marshalling).
    """


class ObjectNotFound(EdgyException):
    """
    Exception raised when a requested object is not found in the database.

    This is commonly used when a query for a single object returns no results.
    """


class MultipleObjectsReturned(EdgyException):
    """
    Exception raised when a query expected to return a single object
    returns multiple objects.

    This helps in enforcing uniqueness constraints where a single result is
    anticipated.
    """


class ImproperlyConfigured(EdgyException):
    """
    Exception raised when Edgy is improperly configured.

    This typically occurs when essential settings, connections, or components
    are missing or incorrectly set up.
    """


class ForeignKeyBadConfigured(EdgyException):
    """
    Exception raised when a ForeignKey relationship is improperly configured.

    This can include issues with referencing non-existent models, incorrect
    `related_name`, or other misconfigurations in foreign key definitions.
    """


class RelationshipIncompatible(EdgyException):
    """
    Exception raised when a defined model relationship is incompatible.

    This signifies a conflict or logical inconsistency in how two models are
    related to each other, preventing the relationship from being established.
    """


class DuplicateRecordError(EdgyException):
    """
    Exception raised when an attempt is made to create a duplicate record
    that violates a unique constraint.

    This indicates an integrity error where a new entry would conflict with an
    existing unique entry in the database.
    """


class ModelCollisionError(EdgyException):
    """
    Exception raised when there is a naming collision between models.

    This can happen if multiple models with the same name are defined in a
    way that causes ambiguity or conflicts within the registry.
    """


class RelationshipNotFound(EdgyException):
    """
    Exception raised when a specified relationship between models cannot be found.

    This occurs when attempting to access or manipulate a relationship that
    does not exist or is not correctly defined.
    """


class QuerySetError(EdgyException):
    """
    Exception raised for errors specific to QuerySet operations.

    This covers a range of issues that can occur during database queries,
    filtering, ordering, or data retrieval.
    """


class ModelReferenceError(EdgyException):
    """
    Exception raised when there is an error in a model reference.

    This can happen if a model refers to another model that is not properly
    defined or accessible within the application's context.
    """


class SchemaError(EdgyException):
    """
    Exception raised when an error occurs related to database schema operations.

    This includes issues during migrations, schema generation, or validation.
    """


class SignalError(EdgyException):
    """
    Exception raised when an error occurs during signal dispatch or handling.

    This indicates problems with the signal mechanism, such as issues with
    connecting receivers or signal processing.
    """


class CommandEnvironmentError(EdgyException):
    """
    Exception raised when there is an error in the command-line
    environment for Edgy.

    This typically relates to issues with environment variables,
    configuration files, or other setup required for CLI commands.
    """


class ModelSchemaError(EdgyException):
    """
    Exception raised for errors specific to a model's schema.

    This indicates problems within the internal representation or validation
    of a model's database schema.
    """


class SuspiciousFileOperation(Exception):
    """
    Exception raised for suspicious file operations, typically for security reasons.

    This is used to prevent potentially malicious file access or manipulation.
    """


class InvalidStorageError(ImproperlyConfigured):
    """
    Exception raised when an invalid storage backend is configured.

    This extends `ImproperlyConfigured` to specifically address issues with
    file storage settings.
    """


class DatabaseNotConnectedWarning(UserWarning):
    """
    Warning raised when a database operation is attempted but the
    database is not connected.

    This serves as a non-critical alert to the user about the connection state.
    """
