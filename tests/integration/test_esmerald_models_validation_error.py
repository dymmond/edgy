import pytest
from esmerald import Esmerald, Gateway, post
from esmerald.testclient import EsmeraldTestClient
from tests.settings import DATABASE_URL

import edgy
from edgy.testclient import DatabaseTestClient as Database

database = Database(url=DATABASE_URL)
models = edgy.Registry(database=database)

pytestmark = pytest.mark.anyio


class User(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True)
    name: str = edgy.CharField(max_length=100)
    email: str = edgy.EmailField(max_length=100)
    language: str = edgy.CharField(max_length=200, null=True)
    description: str = edgy.TextField(max_length=5000, null=True)

    class Meta:
        registry = models


@post("/create")
async def create_user(data: User) -> None:
    ...  # pragma: no cover


app = Esmerald(routes=[Gateway(handler=create_user)])
client = EsmeraldTestClient(app, raise_server_exceptions=True)


def test_raises_error_on_missing_not_null_fields():
    data = {"language": "EN", "description": "A description"}

    response = client.post("/create", json=data)
    assert response.status_code == 400  # Raised by Esmerald when pydantic raises an error
    assert response.json() == {
        "detail": "Validation failed for http://testserver/create with method POST.",
        "errors": [
            {
                "type": "missing",
                "loc": ["name"],
                "msg": "Field required",
                "input": {"language": "EN", "description": "A description"},
                "url": "https://errors.pydantic.dev/2.1/v/missing",
            },
            {
                "type": "missing",
                "loc": ["email"],
                "msg": "Field required",
                "input": {"language": "EN", "description": "A description"},
                "url": "https://errors.pydantic.dev/2.1/v/missing",
            },
        ],
    }
