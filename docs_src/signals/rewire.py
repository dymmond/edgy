import edgy

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


# Overwrite a model lifecycle Signal; this way the main signals.pre_delete is not triggered
User.meta.signals.pre_delete = Signal()

# Update all lifecyle signals. Replace pre_delete again with the default
User.meta.signals.set_lifecycle_signals_from(signals)
