import edgy
from typing import ClassVar
from pydantic import ConfigDict

models = edgy.Registry(
    database="...",
)


class User(edgy.Model):
    name: str = edgy.fields.CharField(max_length=100, unique=True)
    active: bool = edgy.fields.BooleanField(default=False)

    class Meta:
        registry = models

    @classmethod
    def get_admin_marshall_config(cls, *, phase: str, for_schema: bool) -> dict:
        return {"exclude": ["name"]}

    @classmethod
    def get_admin_marshall_class(
        cls: type[edgy.Model], *, phase: str, for_schema: bool = False
    ) -> type[edgy.marshalls.Marshall]:
        """
        Generate a marshall class for the admin.

        Can be dynamic for the current user.
        """

        class AdminMarshall(edgy.marshalls.Marshall):
            # forbid triggers additionalProperties=false
            model_config: ClassVar[ConfigDict] = ConfigDict(
                title=cls.__name__, extra="forbid" if for_schema else None
            )
            marshall_config = edgy.marshalls.ConfigMarshall(
                model=cls,
                **cls.get_admin_marshall_config(phase=phase, for_schema=for_schema),  # type: ignore
            )

        return AdminMarshall
