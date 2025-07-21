from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from edgy.core.db.fields.file_field import FileField
from edgy.core.files import ImageFieldFile
from edgy.exceptions import FieldDefinitionError

if TYPE_CHECKING:
    from edgy.core.db.fields.types import BaseFieldType


class ImageField(FileField):
    """
    An extension of `FileField` specifically designed for handling image files.

    This field automatically sets `with_approval` to `True` by default,
    and integrates with the Pillow library to extract image-specific metadata
    like height and width during the cleaning process. It also supports
    different image formats before and after approval.

    Attributes:
        image_formats (Sequence[str] | None): A sequence of allowed image formats
                                              that can be processed without explicit
                                              approval. Defaults to an empty tuple.
        approved_image_formats (Sequence[str] | None): A sequence of allowed image
                                                      formats that are only processed
                                                      after approval. Defaults to `None`.
        field_file_class (type[ImageFieldFile]): The specific `FieldFile` class
                                                 to use for image operations.
                                                 Defaults to `ImageFieldFile`.
    """

    def __new__(
        cls,
        # Image formats allowed without explicit approval.
        image_formats: Sequence[str] | None = (),
        # Extra image formats allowed only after explicit approval.
        approved_image_formats: Sequence[str] | None = None,
        field_file_class: type[ImageFieldFile] = ImageFieldFile,
        **kwargs: Any,
    ) -> BaseFieldType:
        """
        Creates a new `ImageField` instance.

        This method sets the `with_approval` kwarg to `True` by default for image fields.
        It then delegates the field creation to the parent `FileField`'s `__new__` method,
        passing along image-specific formats and the `ImageFieldFile` class.

        Args:
            image_formats (Sequence[str] | None): Allowed image formats for unapproved files.
            approved_image_formats (Sequence[str] | None): Allowed image formats for approved files.
            field_file_class (type[ImageFieldFile]): The `FieldFile` class to use.
            **kwargs (Any): Additional keyword arguments passed to the `FileField`.

        Returns:
            BaseFieldType: The constructed `ImageField` instance.
        """
        # Ensure that image fields generally require approval.
        kwargs.setdefault("with_approval", True)
        return super().__new__(
            cls,
            field_file_class=field_file_class,
            image_formats=image_formats,
            approved_image_formats=approved_image_formats,
            **kwargs,
        )

    @classmethod
    def extract_metadata(
        cls, field_obj: BaseFieldType, field_name: str, field_file: ImageFieldFile
    ) -> dict[str, Any]:
        """
        Extracts metadata from an image file, including inherited file metadata.

        This method extends the base `FileField.extract_metadata` by specifically
        opening the image file using Pillow and extracting its height and width.
        It handles `UnidentifiedImageError` gracefully if the file is not a valid image.

        Args:
            field_obj (BaseFieldType): The field object itself.
            field_name (str): The name of the field.
            field_file (ImageFieldFile): The `ImageFieldFile` instance from which
                                        to extract metadata.

        Returns:
            dict[str, Any]: A dictionary containing extracted image metadata (height, width)
                            along with any metadata extracted by the parent `FileField`.
        """
        from PIL import UnidentifiedImageError

        # Call the parent method to get base file metadata (e.g., MIME type).
        data: dict[str, Any] = super().extract_metadata(
            field_obj, field_name=field_name, field_file=field_file
        )
        assert isinstance(field_file, ImageFieldFile)

        try:
            # Attempt to open the image using `field_file.open_image()`,
            # which leverages Pillow.
            img = field_file.open_image()
            # Extract height and width.
            data["height"] = img.height
            data["width"] = img.width
            img.close()  # Close the image to release resources.
        except UnidentifiedImageError:
            # If the file is not a recognizable image, gracefully pass without
            # adding height/width metadata.
            pass

        return data

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        """
        Performs validation specific to `ImageField` instances.

        This method overrides the parent `validate` method to ensure that the
        `Pillow` (PIL) library is installed, as it is required for image processing.

        Args:
            kwargs (dict[str, Any]): The dictionary of keyword arguments passed
                                     during field construction.

        Raises:
            FieldDefinitionError: If the `Pillow` library is not found.
        """
        super().validate(kwargs)
        try:
            import PIL  # noqa: F401 (Imported but unused)
        except ImportError:
            raise FieldDefinitionError(
                "pillow library is missing. Cannot use ImageField"
            ) from None
