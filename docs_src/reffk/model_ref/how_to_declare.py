from datetime import datetime

import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class Post(edgy.Model):
    comment: str = edgy.TextField()
    created_at: datetime = edgy.DateTimeField(auto_now_add=True)

    class Meta:
        registry = models
