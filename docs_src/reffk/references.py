from edgy import ModelRef


class PostRef(ModelRef):
    __model__ = "Post"
    comment: str
