from __future__ import annotations

from typing import TYPE_CHECKING, Any

from edgy.core.db.fields.types import BaseFieldType

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo


def extract_field_annotations_and_defaults(
    attrs: dict[Any, Any], base_type: type[FieldInfo] | type[BaseFieldType] = BaseFieldType
) -> tuple[dict[Any, Any], dict[Any, Any]]:
    """
    Extracts field annotations and populates model fields from a class's attribute dictionary.

    This function performs a crucial step in preparing a model's definition by:
    1.  Ensuring that the `__annotations__` key exists within the provided `attrs`
        dictionary, initializing it as an empty dictionary if it's not already present.
        This is fundamental for Python's type hinting system and for Pydantic's
        subsequent validation process.
    2.  Delegating the actual field identification and configuration to the
        `populate_pydantic_default_values` function. This separation of concerns
        allows for a cleaner and more maintainable codebase. The delegated function
        will meticulously go through the attributes, identify Edgy-specific field
        instances, and correctly set up their properties, including their names
        and type annotations, in a way that aligns with both Edgy's internal
        mechanisms and Pydantic's validation requirements.

    Parameters:
        attrs (dict[Any, Any]): The dictionary representing the class namespace,
                                typically obtained via `locals()` during class
                                definition. It contains all attributes defined
                                within the class body, including potential
                                Edgy field instances.
        base_type (type[FieldInfo] | type[BaseFieldType]): The base type used
            to identify what constitutes a "field" within the `attrs` dictionary.
            This allows flexibility to work with either Pydantic's native
            `FieldInfo` objects or Edgy's custom `BaseFieldType` instances.
            It defaults to `BaseFieldType`, indicating a focus on Edgy's
            integrated field system.

    Returns:
        tuple[dict[Any, Any], dict[Any, Any]]: A two-element tuple containing:
            - The modified `attrs` dictionary: This dictionary will have its
              `__annotations__` entry updated to reflect the determined type
              hints for all identified fields.
            - A dictionary of `model_fields`: This dictionary contains the
              configured Edgy field instances, keyed by their respective names.
              These fields are ready for use by Edgy's ORM functionalities
              and Pydantic's validation engine.
    """
    # Ensure '__annotations__' key exists in the attrs dictionary, initializing if not present.
    key = "__annotations__"
    attrs[key] = attrs.get(key, {})
    # Populate Pydantic default values and extract model fields.
    attrs, model_fields = populate_pydantic_default_values(attrs, base_type)
    return attrs, model_fields


def get_model_fields(
    attrs: dict[Any, Any], base_type: type[FieldInfo] | type[BaseFieldType] = BaseFieldType
) -> dict[Any, Any]:
    """
    Retrieves all attributes from a given dictionary that are instances of the specified base field type.

    This utility function serves as a filter, efficiently scanning through the provided
    `attrs` dictionary. It identifies and collects only those key-value pairs where
    the value is an object whose type matches or inherits from the `base_type` parameter.
    This is particularly useful in an ORM context like Edgy, where specific field types
    (e.g., `CharField`, `IntegerField`) are defined to represent database columns.
    By filtering based on `base_type`, this function effectively isolates all declared
    Edgy model fields from other class attributes.

    Parameters:
        attrs (dict[Any, Any]): The dictionary of attributes to inspect. This
                                typically represents the `__dict__` or namespace
                                of a model class, containing all its defined members.
        base_type (type[FieldInfo] | type[BaseFieldType]): The base class or type
            to use for `isinstance()` checks. Only attributes that are instances
            of this type (or its subclasses) will be included in the returned
            dictionary. Defaults to `BaseFieldType`, which is the fundamental
            base for all Edgy field types.

    Returns:
        dict[Any, Any]: A new dictionary containing only the key-value pairs
                        from `attrs` where the value is an instance of `base_type`.
                        The keys will be the attribute names (strings), and the
                        values will be the corresponding field instances.
    """
    # Filter the attributes to include only those that are instances of the base_type.
    return {k: v for k, v in attrs.items() if isinstance(v, base_type)}


def populate_pydantic_default_values(
    attrs: dict[Any, Any], base_type: type[FieldInfo] | type[BaseFieldType] = BaseFieldType
) -> tuple[dict[Any, Any], dict[Any, Any]]:
    """
    Configures Edgy fields within a model's attributes for seamless integration with Pydantic validation.

    This function plays a critical role in bridging Edgy's field definitions with
    Pydantic's data validation capabilities. For each identified Edgy field within
    the `attrs` dictionary, it performs the following essential steps:
    1.  **Name Assignment**: Assigns the correct field name (the attribute's key in `attrs`)
        to the `field.name` property of the Edgy field instance. This ensures that
        the field object itself knows its logical name within the model.
    2.  **Type Annotation Determination**:
        * It intelligently determines the appropriate Python type annotation
            for the field. This involves checking if the field is nullable.
        * If `field.null` is `True`, the annotation becomes `None | field.field_type`
            (using Python 3.10+ union syntax), correctly indicating that the field
            can hold either its defined type or `None`.
        * If `field.null` is `False`, the annotation is simply `field.field_type`.
        * It also considers an `__original_type__` attribute on the field, allowing
            for potential type overrides or preservation of generic types. If an
            `original_type` exists and differs from the computed `field.field_type`,
            the `original_type` is preferred for the annotation. This ensures that
            complex or generic type hints defined by the user are maintained.
    3.  **Annotation Update**: Updates the model's `__annotations__` dictionary with
        the determined type annotation for the current field. This is crucial
        because Pydantic (and Python's type system) relies on this `__annotations__`
        dictionary to perform validation and introspection.
    4.  **Field Collection**: Adds the fully configured Edgy field instance to a
        `model_fields` dictionary. This dictionary will be returned and used
        internally by Edgy for ORM operations and model management.

    By performing these steps, this function ensures that Edgy model fields are
    correctly interpreted and validated by Pydantic, while also maintaining
    the necessary metadata for Edgy's database interactions.

    Parameters:
        attrs (dict[Any, Any]): The class attributes dictionary where potential
                                Edgy fields are defined. This dictionary is
                                modified in place (specifically, its
                                `__annotations__` entry).
        base_type (type[FieldInfo] | type[BaseFieldType]): The base type used to
            identify field instances within `attrs`. Defaults to `BaseFieldType`,
            ensuring that only Edgy-specific fields are processed.

    Returns:
        tuple[dict[Any, Any], dict[Any, Any]]: A two-element tuple containing:
            - The `attrs` dictionary: This dictionary, after being processed,
              will have its `__annotations__` key fully populated with the
              correct type hints for all Edgy fields.
            - A dictionary of `model_fields`: This dictionary contains all
              the identified and configured Edgy field instances, ready for
              use by Edgy's ORM and Pydantic's validation.
    """
    model_fields = {}
    potential_fields: dict[Any, Any] = {}

    # Identify all attributes within 'attrs' that are instances of the specified base_type.
    # These are considered the potential Edgy fields that need to be processed.
    potential_fields.update(get_model_fields(attrs, base_type))

    # Iterate through each identified potential field (key-value pair).
    for field_name, field in potential_fields.items():
        # Assign the field's logical name based on its attribute name in the class.
        field.name = field_name
        # Attempt to retrieve the '__original_type__' attribute from the field.
        # This is used for maintaining specific user-defined generic types.
        original_type = getattr(field, "__original_type__", None)

        # Determine the default type annotation for the field.
        # If 'field.null' is True, the type becomes a Union with None (Python 3.10+ syntax).
        # Otherwise, it's just the field's inherent 'field_type'.
        default_type = field.field_type if not field.null else None | field.field_type
        # Decide if the 'original_type' should override the 'default_type'.
        # This happens if 'original_type' exists and is different from 'field.field_type'.
        overwrite_type = original_type if field.field_type != original_type else None
        # Set the final annotation for the field instance.
        field.annotation = overwrite_type or default_type

        # Add the configured field instance to the 'model_fields' dictionary,
        # keyed by its name. This dictionary collects all processed Edgy fields.
        model_fields[field_name] = field
        # Update the '__annotations__' dictionary of the class. This makes the
        # type hints visible to Pydantic for validation and to static type checkers.
        attrs["__annotations__"][field_name] = overwrite_type or default_type
    return attrs, model_fields
