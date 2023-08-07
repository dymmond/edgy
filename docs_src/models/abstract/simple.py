import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class BaseModel(edgy.Model):
    class Meta:
        abstract = True
        registry = models
