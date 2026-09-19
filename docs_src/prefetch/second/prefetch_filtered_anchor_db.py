import edgy
from edgy import Prefetch

models1 = edgy.Registry(database="sqlite:///db.sqlite")
models2 = edgy.Registry(database="sqlite:///db.sqlite")


class Track(edgy.Model):
    id = edgy.BigIntegerField(primary_key=True, autoincrement=True)
    album = edgy.ForeignKey("Album", on_delete=edgy.CASCADE, related_name="tracks")
    title = edgy.CharField(max_length=100)
    position = edgy.IntegerField()

    class Meta:
        registry = models1


class Album(edgy.Model):
    name = edgy.CharField(max_length=255)

    class Meta:
        registry = models1


class Studio(edgy.Model):
    album = edgy.ForeignKey("Album", related_name="studios")
    name = edgy.CharField(max_length=255)

    class Meta:
        registry = models1


class Company(edgy.Model):
    studio = edgy.ForeignKey(Studio, related_name="companies")

    class Meta:
        registry = models2


# All the tracks that belong to a specific `Company`.
# The tracks are associated with `albums` and `studios`
# where the `Track` will be also internally filtered
company = await Company.query.prefetch_related(
    Prefetch(
        related_name="tracks",
        to_attr="tracks_filtered",
        queryset=Track.query.filter(title__icontains="bird"),
        from_anchor="studio__album",
    )
).get()
assert company.tracks_filtered
