from datetime import datetime

import edgy
from edgy import Database, ModelRef, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class Post(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True)
    comment: str = edgy.TextField()
    created_at: datetime = edgy.DateTimeField(auto_now_add=True)

    class Meta:
        registry = models


class PostRef(ModelRef):
    __related_name__ = "posts_set"
    comment: str
    created_at: datetime
