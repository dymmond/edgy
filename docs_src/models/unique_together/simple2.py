import saffier
from saffier import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(saffier.Model):
    name = saffier.CharField(max_length=255)
    email = saffier.EmailField(max_length=70)
    is_active = saffier.BooleanField(default=True)

    class Meta:
        registry = models
        unique_together = ["name"]  # or ("name",)
