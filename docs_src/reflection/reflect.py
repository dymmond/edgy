import saffier
from saffier import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(saffier.ReflectModel):
    age = saffier.IntegerField(minimum=18)
    is_active = saffier.BooleanField(default=True)

    class Meta:
        tablename = "users"
        registry = models
