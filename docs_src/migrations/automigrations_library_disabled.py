import edgy
from monkay import ExtensionProtocol
from edgy import Registry, EdgySettings


class User(edgy.Model):
    age: int = edgy.IntegerField(gte=18)
    is_active: bool = edgy.BooleanField(default=True)


class AddUserExtension(ExtensionProtocol):
    name = "add_user"

    def apply(self, monkay_instance):
        User.add_to_registry(monkay_instance.registry)


class LibraryConfig(EdgySettings):
    extensions = [AddUserExtension()]


class Config(EdgySettings):
    allow_automigrations = False


async def create_custom_registry():
    return Registry("DB_URL", automigrate_on_connect=LibraryConfig)


def get_application():
    edgy.monkay.settings = Config
    return Registry("DB_URL").asgi(...)


app = create_custom_registry().asgi(get_application())

# get sql migrations with
# edgy -d library/migrations_folder migrate --sql
# this is also the way for downgrades as automigrations does only work for upgrades
