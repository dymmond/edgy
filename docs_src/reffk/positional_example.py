from typing import List

import edgy
from edgy import Database, Registry, run_sync

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class PostRef(ModelRef):
    __related_name__ = "posts_set"
    comment: str


class User(edgy.Model):
    name: str = edgy.CharField(max_length=255)

    class Meta:
        registry = models


class Post(edgy.Model):
    user: User = edgy.ForeignKey(User)
    comment: str = edgy.TextField()

    class Meta:
        registry = models


# This time completely without a RefForeignKey

run_sync(
    User.query.create(
        PostRef(comment="foo"),
        PostRef(comment="bar"),
    )
)
