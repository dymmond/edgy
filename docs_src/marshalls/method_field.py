from typing import Any, Dict

from pydantic import BaseModel
from tests.settings import DATABASE_URL

import edgy
from edgy.core.marshalls import Marshall, fields
from edgy.core.marshalls.config import ConfigMarshall
from edgy.testclient import DatabaseTestClient as Database

database = Database(url=DATABASE_URL)
registry = edgy.Registry(database=database)


class User(edgy.Model):
    name: str = edgy.CharField(max_length=100, null=False)
    email: str = edgy.EmailField(max_length=100, null=False)
    language: str = edgy.CharField(max_length=200, null=True)
    description: str = edgy.TextField(max_length=5000, null=True)

    class Meta:
        registry = registry

    @property
    def display_name(self) -> str:
        return f"Diplay name: {self.name}"


class UserExtra(BaseModel):
    address: str
    post_code: str


class UserMarshall(Marshall):
    marshall_config: ConfigMarshall = ConfigMarshall(
        model=User,
        exclude=["language"],
    )
    display_name: fields.MarshallMethodField = fields.MarshallMethodField(field_type=str)
    data: fields.MarshallMethodField = fields.MarshallMethodField(field_type=Dict[str, Any])

    def get_display_name(self, instance: edgy.Model) -> str:
        return instance.display_name()

    def get_data(self, instance: edgy.Model) -> Dict[str, Any]:
        extra = UserExtra(address="123 street", post_code="90210")
        return extra.model_dump()
