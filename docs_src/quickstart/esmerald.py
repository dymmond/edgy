from esmerald import Esmerald, Gateway, post

import edgy
from edgy.testclient import DatabaseTestClient as Database

database = Database("sqlite:///db.sqlite")
models = edgy.Registry(database=database)


class User(edgy.Model):
    name: str = edgy.CharField(max_length=100)
    email: str = edgy.EmailField(max_length=100)
    language: str = edgy.CharField(max_length=200, null=True)
    description: str = edgy.TextField(max_length=5000, null=True)

    class Meta:
        registry = models


@post("/create")
async def create_user(data: User) -> User:
    """
    You can perform the same directly like this
    as the validations for the model (nulls, mandatories, @field_validators)
    already did all the necessary checks defined by you.
    """
    user = await data.save()
    return user


app = models.asgi(
    Esmerald(
        routes=[Gateway(handler=create_user)],
    )
)
