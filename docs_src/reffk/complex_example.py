from typing import List

import edgy
from edgy import Database, Registry

from .references import PostRef

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True)
    name: str = edgy.CharField(max_length=255)
    posts: List["Post"] = edgy.RefForeignKey(PostRef)

    class Meta:
        registry = models


class Post(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True)
    user: User = edgy.ForeignKey(User)
    comment: str = edgy.TextField()

    class Meta:
        registry = models
