import edgy
from edgy.contrib.contenttypes import ContentType as BaseContentType


class ContentType(BaseContentType):
    system_message: str = edgy.fields.CharField(default="", max_length=20)

    class Meta:
        abstract = True
        # we can create it now
        no_admin_create = False

    @classmethod
    def get_admin_marshall_config(cls, *, phase: str, for_schema: bool) -> dict:
        return {"exclude": ["system_message"]}


models = edgy.Registry(
    database="...",
    with_content_type=ContentType,
)
