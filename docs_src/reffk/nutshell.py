from typing import List

import edgy
from edgy import Database, ModelRef, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class PostRef(ModelRef):
    __related_name__ = "posts_set"
    comment: str


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
