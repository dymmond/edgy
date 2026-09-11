import edgy
from edgy import Prefetch

database = edgy.Database("sqlite:///db.sqlite")
models = edgy.Registry(database=database)

# All the tracks that belong to a specific `Company`.
# The tracks are associated with `albums` and `studios`
# where the `Track` will be also internally filtered
company = (
    await Company.query.select_related("studio__album")
    .prefetch_related(
        Prefetch(
            related_name="tracks",
            to_attr="tracks_filtered",
            queryset=Track.query.filter(title__icontains="bird"),
            from_anchor="studio__album",
        )
    )
    .get()
)
