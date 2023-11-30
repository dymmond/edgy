import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    name: str = edgy.CharField(max_length=50)
    email: str = edgy.EmailField(max_lengh=100)
    password: str = edgy.CharField(max_length=1000, secret=True)

    class Meta:
        registry = models
