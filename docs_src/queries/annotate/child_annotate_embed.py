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
    profile = edgy.fields.OneToOne(
        "SuperProfile", related_name="profile", embed_parent=("user", "normal_profile")
    )

    class Meta:
        registry = models


class SuperProfile(edgy.Model):
    name = edgy.CharField(max_length=100)

    class Meta:
        registry = models


for profile in await SuperProfile.query.all():
    user = (
        await profile.profile.select_related("user")
        .reference_select({"user": {"profile_name": "name"}})
        .get()
    )
    assert isinstance(user, User)
    assert user.normal_profile.name == user.profile_name
