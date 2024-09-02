from typing import TYPE_CHECKING, Any, Dict, Optional, Sequence, Type

from edgy.core.db.fields.file_field import FileField
from edgy.core.files import FieldFile
from edgy.exceptions import FieldDefinitionError

if TYPE_CHECKING:
    from PIL.ImageFile import ImageFile

    from edgy.core.db.fields.types import BaseFieldType


class ImageFieldFile(FieldFile):
    def open_image(self) -> "ImageFile":
        from PIL import Image

        allowed_formats: Optional[Sequence[str]] = getattr(self.field, "image_formats", ())
        if self.approved and allowed_formats is not None:
            approved_image_formats: Optional[Sequence[str]] = getattr(
                self.field, "approved_image_formats", ()
            )
            if approved_image_formats is None:
                allowed_formats = None
            else:
                allowed_formats = (*allowed_formats, *approved_image_formats)
        return Image.open(self.open("rb"), formats=allowed_formats)


class ImageField(FileField):
    def __new__(  # type: ignore
        cls,
        # image formats without approval
        image_formats: Optional[Sequence[str]] = (),
        # extra image formats after approval
        approved_image_formats: Optional[Sequence[str]] = None,
        field_file_class: Type[ImageFieldFile] = ImageFieldFile,
        **kwargs: Dict[str, Any],
    ) -> "BaseFieldType":
        return super().__new__(
            cls,
            image_formats=image_formats,
            approved_image_formats=approved_image_formats,
            **kwargs,
        )  # type: ignore

    @classmethod
    def extract_metadata(
        cls, field_obj: "BaseFieldType", field_name: str, field_file: FieldFile
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = super().extract_metadata(
            field_obj, field_name=field_name, field_file=field_file
        )

        img = field_file.open_image()
        data["height"] = img.height
        data["width"] = img.width
        img.close()

        return data

    @classmethod
    def validate(cls, kwargs: Dict[str, Any]) -> None:
        super().validate(kwargs)
        try:
            import PIL  # noqa: F401
        except ImportError:
            raise FieldDefinitionError(
                "pillow library is missing. Cannot use ImageField"
            ) from None
