import edgy
from edgy import Prefetch

database = edgy.Database("sqlite:///db.sqlite")
models = edgy.Registry(database=database)


class User(edgy.Model):
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Post(edgy.Model):
    user = edgy.ForeignKey(User, related_name="posts")
    comment = edgy.CharField(max_length=255)

    class Meta:
        registry = models


class Article(edgy.Model):
    user = edgy.ForeignKey(User, related_name="articles")
    content = edgy.CharField(max_length=255)

    class Meta:
        registry = models


# All the users with all the posts and articles
# of each user
users = await User.query.prefetch_related(
    Prefetch(related_name="posts", to_attr="to_posts"),
    Prefetch(related_name="articles", to_attr="to_articles"),
).all()
