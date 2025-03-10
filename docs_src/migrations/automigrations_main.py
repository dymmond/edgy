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
    extensions = [AddUserExtension()]


async def create_custom_registry():
    return Registry("DB_URL", automigrate_on_connect=LibraryConfig)


def get_application():
    edgy.monkay.settings = Config
    return Registry("DB_URL").asgi(...)


app = get_application()
