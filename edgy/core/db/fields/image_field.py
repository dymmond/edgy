from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Optional

from edgy.core.db.fields.file_field import FileField
from edgy.core.files import ImageFieldFile
from edgy.exceptions import FieldDefinitionError

if TYPE_CHECKING:
    from edgy.core.db.fields.types import BaseFieldType


class ImageField(FileField):
    def __new__(  # type: ignore
        cls,
        # image formats without approval
        image_formats: Optional[Sequence[str]] = (),
        # extra image formats after approval
        approved_image_formats: Optional[Sequence[str]] = None,
        field_file_class: type[ImageFieldFile] = ImageFieldFile,
        **kwargs: Any,
    ) -> "BaseFieldType":
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
        cls, field_obj: "BaseFieldType", field_name: str, field_file: "ImageFieldFile"
    ) -> dict[str, Any]:
        from PIL import UnidentifiedImageError

        data: dict[str, Any] = super().extract_metadata(
            field_obj, field_name=field_name, field_file=field_file
        )
        assert isinstance(field_file, ImageFieldFile)
        # here the formats are checked
        try:
            img = field_file.open_image()
            data["height"] = img.height
            data["width"] = img.width
            img.close()
        except UnidentifiedImageError:
            pass

        return data

    @classmethod
    def validate(cls, kwargs: dict[str, Any]) -> None:
        super().validate(kwargs)
        try:
            import PIL  # noqa: F401
        except ImportError:
            raise FieldDefinitionError(
                "pillow library is missing. Cannot use ImageField"
            ) from None
