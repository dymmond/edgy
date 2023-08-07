import saffier
from saffier import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class BaseModel(saffier.Model):
    class Meta:
        abstract = True
        registry = models
