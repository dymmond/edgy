import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    is_active: bool = edgy.BooleanField(default=True)
    first_name: str = edgy.CharField(max_length=50)
    last_name: str = edgy.CharField(max_length=50)
    email: str = edgy.EmailField(max_lengh=100)
    password: str = edgy.CharField(max_length=1000)

    class Meta:
        registry = models


class Thread(edgy.Model):
    sender: User = edgy.ForeignKey(
        User,
        on_delete=edgy.CASCADE,
        related_name="sender",
    )
    receiver: User = edgy.ForeignKey(
        User,
        on_delete=edgy.CASCADE,
        related_name="receiver",
    )
    message: str = edgy.TextField()

    class Meta:
        registry = models
