import sqlalchemy
from sqlalchemy import func

import edgy

models = edgy.Registry(database=...)


class User(edgy.Model):
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class Profile(edgy.Model):
    user = edgy.fields.OneToOne(User, related_name="profile")
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


for profile in await Profile.query.extra_select(
    func.count()
    .select()
    .select_from((await User.query.as_select()).subquery())
    .label("total_number")
).reference_select({"total_number": "total_number"}):
    assert profile.total_number == 10


# or manually
for profile in await Profile.query.extra_select(
    sqlalchemy.select(func.count(User.table.c.id).label("total_number")).subquery()
).reference_select({"total_number": "total_number"}):
    assert profile.total_number >= 0
