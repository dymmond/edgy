import edgy


class BaseModel(edgy.StrictModel):
    protected = edgy.BooleanField(default=False)
    __deletion_with_signals__ = True
    __require_model_based_deletion__ = True

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
@Friend.meta.signals.pre_relation_remove.connect_via(Friend.meta.fields["users"].through)
@Profile.meta.signals.pre_relation_remove.connect_via(Profile)
async def abort_removal_relation(sender, raw_values, **kwargs):
    for value in raw_values:
        if value.protected:
            raise Exception()


@User.meta.signals.pre_delete.connect_via(User)
@Friend.meta.signals.pre_delete.connect_via(Friend.meta.fields["users"].through)
@Profile.meta.signals.pre_delete.connect_via(Profile)
async def abort_removal_relation(sender, model_instance, **kwargs):
    if model_instance.protected:
        raise Exception()
