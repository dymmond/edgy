import edgy
from edgy.core import signals
from edgy import Signal
# or:
# from blinker import Signal

database = edgy.Database("sqlite:///db.sqlite")
registry = edgy.Registry(database=database)


class User(edgy.Model):
    id: int = edgy.BigIntegerField(primary_key=True)
    name: str = edgy.CharField(max_length=255)
    email: str = edgy.CharField(max_length=255)

    class Meta:
        registry = registry


# Create the custom signal
User.meta.signals.on_verify = Signal()
