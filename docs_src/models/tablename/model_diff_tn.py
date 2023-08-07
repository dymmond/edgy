import saffier
from saffier import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(saffier.Model):
    name = saffier.CharField(max_length=255)
    is_active = saffier.BooleanField(default=True)

    class Meta:
        tablename = "db_users"
        registry = models
