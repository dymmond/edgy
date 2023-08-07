import saffier
from saffier import Database, Registry, UniqueConstraint

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(saffier.Model):
    name = saffier.CharField(max_length=255)
    email = saffier.EmailField(max_length=70)
    phone_number = saffier.CharField(max_length=15)
    address = saffier.CharField(max_length=500)
    is_active = saffier.BooleanField(default=True)

    class Meta:
        registry = models
        unique_together = [
            UniqueConstraint(fields=["name", "email"]),
            UniqueConstraint(fields=["name", "email", "phone_number"]),
            UniqueConstraint(fields=["email", "address"]),
        ]
