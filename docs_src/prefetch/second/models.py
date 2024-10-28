import edgy

database = edgy.Database("sqlite:///db.sqlite")
models = edgy.Registry(database=database)


class Album(edgy.Model):
    id = edgy.IntegerField(primary_key=True, autoincrement=True)
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Track(edgy.Model):
    id = edgy.BigIntegerField(primary_key=True, autoincrement=True)
    album = edgy.ForeignKey("Album", on_delete=edgy.CASCADE, related_name="tracks")
    title = edgy.CharField(max_length=100)
    position = edgy.IntegerField()

    class Meta:
        registry = models


class Studio(edgy.Model):
    album = edgy.ForeignKey("Album", related_name="studios")
    name = edgy.CharField(max_length=255)

    class Meta:
        registry = models


class Company(edgy.Model):
    studio = edgy.ForeignKey(Studio, related_name="companies")

    class Meta:
        registry = models
