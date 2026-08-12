from sqlalchemy import ForeignKey
import edgy
from contextvars import ContextVar
from edgy.core import signals

models = edgy.Registry(...)
current_user = ContextVar("current_user", default=None)


class BaseModel(edgy.StrictModel):
    class Meta:
        registry = models
        abstract = True


class Friend(BaseModel):
    name = edgy.CharField(max_length=100)


class Profile(BaseModel):
    name = edgy.CharField(max_length=100)


class User(BaseModel):
    name = edgy.CharField(max_length=100)
    profile = edgy.ForeignKey("Profile", null=True, on_delete=edgy.CASCADE, related_name="users")
    friends = edgy.ManyToMany("Friend", related_name="users")


class Log(BaseModel):
    signal = edgy.CharField(max_length=255)
    class_name = edgy.CharField(max_length=255)
    params = edgy.JSONField()
    user = edgy.ForeignKey(User, null=True, on_delete=edgy.CASCADE, related_name="logs")

    def __str__(self) -> str:
        return str(self.extract_db_fields())

    def __repr__(self) -> str:
        return f"Log<{self}>"


for signal_name in dir(signals):
    if not signal_name.startswith("post_") or signal_name == "post_migrate":
        continue
    signal: signals.Signal = getattr(signals, signal_name)

    async def log(sender, _signal_name=signal_name, **kwargs):
        await Log.query.create(
            signal=_signal_name,
            class_name=sender.__name__,
            params={k: str(v) for k, v in kwargs.items()},
            user=current_user.get(),
        )

    for model in models.models.values():
        if model is not Log:
            # weak must be False otherwise the receivers vanish
            signal.connect(log, model, weak=False)
