import saffier
from saffier import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(saffier.Model):
    age = saffier.IntegerField(minimum=18, null=True)
    is_active = saffier.BooleanField(default=True, null=True)
    description = saffier.CharField(max_length=255, null=True)
    profile_type = saffier.CharField(max_length=255, null=True)
    username = saffier.CharField(max_length=255, null=True)

    class Meta:
        registry = models
