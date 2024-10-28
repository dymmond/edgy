import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    name: str = edgy.CharField(max_length=255)

    class Meta:
        registry = models


class Post(edgy.Model):
    user: User = edgy.ForeignKey(User)
    comment: str = edgy.TextField()

    class Meta:
        registry = models
