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
    __model__ = Post
    comment: str
    created_at: datetime
