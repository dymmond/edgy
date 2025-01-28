import sqlalchemy

import edgy

models = edgy.Registry(database=...)


class User(edgy.StrictModel):
    name = edgy.CharField(max_length=100)
    profile_name = edgy.fields.PlaceholderField(null=True)

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

for profile in await Profile.query.reference_select({"user": {"profile_name": "name"}}):
    assert profile.user.profile_name == profile.name
