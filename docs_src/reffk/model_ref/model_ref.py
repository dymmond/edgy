from datetime import datetime

from edgy import Database, ModelRef, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class PostRef(ModelRef):
    __model__ = "Post"
    comment: str
    created_at: datetime
