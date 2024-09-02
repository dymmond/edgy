from datetime import datetime

from edgy import Database, ModelRef, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class PostRef(ModelRef):
    __related_name__ = "posts_set"
    comment: str
    created_at: datetime
