import edgy
from edgy.exceptions import SkipOperation


class BaseModel(edgy.StrictModel):
    protected = edgy.BooleanField(default=False)

    class Meta:
        registry = ...
        abstract = True


class Friend(BaseModel):
    name = edgy.CharField(max_length=100)


class Profile(BaseModel):
    name = edgy.CharField(max_length=100)


class User(BaseModel):
    name = edgy.CharField(max_length=100)
    profile = edgy.ForeignKey("Profile", null=True, on_delete=edgy.CASCADE, related_name="users")
    friends = edgy.ManyToMany("Friend", related_name="users")


@User.meta.signals.pre_relation_remove.connect_via(User)
@Profile.meta.signals.pre_relation_remove.connect_via(Profile)
async def excempt_removal_relation(sender, raw_values, **kwargs):
    new_raw_values = list(raw_values)
    raw_values.clear()
    for value in new_raw_values:
        if not value.protected:
            raw_values.append(value)


@User.meta.signals.pre_delete.connect_via(User)
@Profile.meta.signals.pre_delete.connect_via(Profile)
async def abort_removal_relation(sender, model_instance, injected_filters, **kwargs):
    if model_instance is None:
        injected_filters.append({"protected": True})
    else:
        if model_instance.protected:
            raise SkipOperation()
