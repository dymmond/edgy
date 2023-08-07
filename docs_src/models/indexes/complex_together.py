import saffier
from saffier import Database, Index, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(saffier.Model):
    name = saffier.CharField(max_length=255)
    email = saffier.EmailField(max_length=70)
    is_active = saffier.BooleanField(default=True)
    status = saffier.CharField(max_length=255)

    class Meta:
        registry = models
        indexes = [
            Index(fields=["name", "email"]),
            Index(fields=["is_active", "status"], name="active_status_idx"),
        ]
