import saffier
from saffier import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class Profile(saffier.ReflectModel):
    is_active = saffier.BooleanField(default=True, null=True)
    profile_type = saffier.CharField(max_length=255, null=True)
    username = saffier.CharField(max_length=255, null=True)

    class Meta:
        tablename = "users"
        registry = models
