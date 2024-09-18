from esmerald import Esmerald, Gateway, post
from pydantic import field_validator

import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class PostRef(edgy.ModelRef):
    __related_name__ = "posts_set"
    comment: str

    @field_validator("comment", mode="before")
    def validate_comment(cls, comment: str) -> str:
        """
        We want to store the comments as everything uppercase.
        """
        comment = comment.upper()
        return comment


class User(edgy.Model):
    id: int = edgy.IntegerField(primary_key=True)
    name: str = edgy.CharField(max_length=100)
    email: str = edgy.EmailField(max_length=100)
    language: str = edgy.CharField(max_length=200, null=True)
    description: str = edgy.TextField(max_length=5000, null=True)
    posts: PostRef = edgy.RefForeignKey(PostRef)

    class Meta:
        registry = models


class Post(edgy.Model):
    user = edgy.ForeignKey("User")
    comment = edgy.CharField(max_length=255)

    class Meta:
        registry = models


@post("/create")
async def create_user(data: User) -> User:
    """
    We want to create a user and update the return model
    with the total posts created for that same user and the
    comment generated.
    """
    user = await data.save()
    posts = await Post.query.filter(user=user)
    return_user = user.model_dump(exclude={"posts"})
    return_user["total_posts"] = len(posts)
    return_user["comment"] = posts[0].comment
    return return_user


def app():
    app = models.asgi(
        Esmerald(
            routes=[Gateway(handler=create_user)],
        )
    )
    return app
