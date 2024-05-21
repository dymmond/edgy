from tests.settings import DATABASE_URL

import edgy
from edgy.core.marshalls import Marshall
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


class UserMarshall(Marshall):
    marshall_config: ConfigMarshall = ConfigMarshall(
        model=User,
        exclude=["language"],
    )
