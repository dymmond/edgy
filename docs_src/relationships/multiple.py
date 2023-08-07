import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    is_active = edgy.BooleanField(default=True)
    first_name = edgy.CharField(max_length=50)
    last_name = edgy.CharField(max_length=50)
    email = edgy.EmailField(max_lengh=100)
    password = edgy.CharField(max_length=1000)

    class Meta:
        registry = models


class Thread(edgy.Model):
    sender = edgy.ForeignKey(
        User,
        on_delete=edgy.CASCADE,
        related_name="sender",
    )
    receiver = edgy.ForeignKey(
        User,
        on_delete=edgy.CASCADE,
        related_name="receiver",
    )
    message = edgy.TextField()

    class Meta:
        registry = models
