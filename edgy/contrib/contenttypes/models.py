from typing import Any

import edgy


class ContentType(edgy.Model):
    class Meta:
        abstract = True

    # model names shouldn't be so long, maybe a check would be appropriate
    model_name: str = edgy.fields.CharField(max_length=100)
    hash_key: str = edgy.fields.CharField(max_length=255, null=True, unique=True)

    def get_models(self) -> Any:
        # FIXME: the return type should be MultiRelation/Queryset
        reverse_name = f"reverse_{self.model_name.lower()}"
        return getattr(self, reverse_name)
