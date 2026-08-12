import edgy


class BaseModel(edgy.StrictModel):
    active = edgy.IntegerField(default=0)
    duplicate: bool = False

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


@User.meta.signals.pre_bulk.connect_via(User)
@Profile.meta.signals.pre_bulk.connect_via(Profile)
async def handle_active_duplicate_bulk(sender, raw_values, create_params, update_params, **kwargs):
    for item in create_params:
        if item[0].active > 0:
            item[0].active = 0

    for item in update_params:
        if item[0].active > 0:
            item[0].active -= 1
        if item[0].duplicate:
            create_params.append((item[0].model_copy(), item[1], item[2]))
