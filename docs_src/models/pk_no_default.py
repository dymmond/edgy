import saffier
from saffier import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(saffier.Model):
    id = saffier.CharField(max_length=255, primary_key=True)
    age = saffier.IntegerField(minimum=18)
    is_active = saffier.BooleanField(default=True)

    class Meta:
        registry = models
