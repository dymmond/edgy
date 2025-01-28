import sqlalchemy

import edgy
from edgy.core.utils.db import hash_tablekey

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


for profile in await Profile.query.select_related("user").reference_select(
    {"user_name": sqlalchemy.text(f"user__name")}
):
    assert profile.user_name == profile.user.name


# manual way
join_table_key = hash_tablekey(tablekey=User.table.key, prefix="user")
for profile in await Profile.query.select_related("user").reference_select(
    {"user_name": sqlalchemy.text(f"{join_table_key}_name")}
):
    assert profile.user_name == profile.user.name
