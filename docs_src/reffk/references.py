from edgy import ModelRef


class PostRef(ModelRef):
    __related_name__ = "posts_set"
    comment: str
