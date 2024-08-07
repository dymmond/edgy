import edgy
from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class Address(edgy.Model):
    street = edgy.CharField(max_length=100)
    city = edgy.CharField(max_length=100)

    class Meta:
        # we don't want a table just a template
        abstract = True


class User(edgy.Model):
    is_active: bool = edgy.BooleanField(default=True)

    class Meta:
        registry = models


class Profile(edgy.Model):
    name: str = edgy.CharField(max_length=100)
    user: User = edgy.OneToOne("User", on_delete=edgy.CASCADE, embed_parent=("address", "profile"))
    address: Address = Address

    class Meta:
        registry = models


user = edgy.run_sync(User.query.create())
edgy.run_sync(
    Profile.query.create(
        name="edgy", user=user, address={"street": "Rainbowstreet 123", "city": "London"}
    )
)
# use the reverse link
address = edgy.run_sync(user.profile.get())
# access the profile
address.profile
