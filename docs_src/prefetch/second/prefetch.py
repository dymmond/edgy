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


# All the tracks that belong to a specific `Company`.
# The tracks are associated with `albums` and `studios`
company = await Company.query.prefetch_related(
    Prefetch(related_name="studio__album__tracks", to_attr="tracks")
).get(studio=studio)
