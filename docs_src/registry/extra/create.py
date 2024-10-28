import edgy
from edgy.core.db import fields
from edgy.testclient import DatabaseTestClient as Database

database = Database("<YOUR-CONNECTION-STRING>")
alternative = Database("<YOUR-ALTERNATIVE-CONNECTION-STRING>")
models = edgy.Registry(database=database, extra={"alternative": alternative})


class User(edgy.Model):
    name: str = fields.CharField(max_length=255)
    email: str = fields.CharField(max_length=255)

    class Meta:
        registry = models


async def bulk_create_users() -> None:
    """
    Bulk creates some users.
    """
    await User.query.using(database="alternative").bulk_create(
        [
            {"name": "Edgy", "email": "edgy@example.com"},
            {"name": "Edgy Alternative", "email": "edgy.alternative@example.com"},
        ]
    )
