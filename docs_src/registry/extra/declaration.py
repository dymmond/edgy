import edgy
from edgy.core.db import fields
from edgy.testclient import DatabaseTestClient as Database

database = Database("<YOUR-CONNECTION-STRING>")
alternative = Database("<YOUR-ALTERNATIVE-CONNECTION-STRING>")
models = edgy.Registry(database=database, extra={"alternative": alternative})


class User(edgy.Model):
    id: int = fields.IntegerField(primary_key=True)
    name: str = fields.CharField(max_length=255)
    email: str = fields.CharField(max_length=255)

    class Meta:
        registry = models
