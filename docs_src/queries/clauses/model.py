import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    first_name: str = edgy.CharField(max_length=50, null=True)
    email: str = edgy.EmailField(max_lengh=100, null=True)

    class Meta:
        registry = models
