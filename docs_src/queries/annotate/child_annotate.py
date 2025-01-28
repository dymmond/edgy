import sqlalchemy

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


for profile in await Profile.query.select_related("profile").reference_select(
    {"user": {"profile_name": "name"}}
):
    assert profile.user.profile_name == profile.name

# up to one level you can leave out the select_related()
# you can also reference columns in case you use them of the main table or explicitly provided via extra_select

for profile in await Profile.query.reference_select(
    {"user": {"profile_name": Profile.table.c.name}}
):
    assert profile.user.profile_name == profile.name
