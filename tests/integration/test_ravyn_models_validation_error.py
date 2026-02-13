import pytest
from pydantic import __version__
from ravyn import Gateway, Ravyn, post
from ravyn.testclient import RavynTestClient

import edgy
from edgy.testclient import DatabaseTestClient
from tests.settings import DATABASE_URL

database = DatabaseTestClient(DATABASE_URL)
models = edgy.Registry(database=edgy.Database(database, force_rollback=True))

pytestmark = pytest.mark.anyio

pydantic_version = ".".join(__version__.split(".")[:2])


class User(edgy.StrictModel):
    id: int = edgy.IntegerField(primary_key=True, autoincrement=True)
    name: str = edgy.CharField(max_length=100)
    email: str = edgy.EmailField(max_length=100)
    language: str = edgy.CharField(max_length=200, null=True)
    description: str = edgy.TextField(max_length=5000, null=True)

    class Meta:
        registry = models


@post("/create")
async def create_user(data: User) -> None: ...  # pragma: no cover


app = Ravyn(routes=[Gateway(handler=create_user)])
client = RavynTestClient(app, raise_server_exceptions=True)


def test_raises_error_on_missing_not_null_fields():
    data = {"language": "EN", "description": "A description"}

    response = client.post("/create", json=data)
    assert response.status_code == 400  # Raised by Ravyn when pydantic raises an error
    assert response.json() == {
        "detail": "Validation failed for http://testserver/create with method POST.",
        "errors": [
            {
                "type": "missing",
                "loc": ["name"],
                "msg": "Field required",
                "input": {"language": "EN", "description": "A description"},
                "url": f"https://errors.pydantic.dev/{pydantic_version}/v/missing",
            },
            {
                "type": "missing",
                "loc": ["email"],
                "msg": "Field required",
                "input": {"language": "EN", "description": "A description"},
                "url": f"https://errors.pydantic.dev/{pydantic_version}/v/missing",
            },
        ],
    }
