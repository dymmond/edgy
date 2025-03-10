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


async def create_custom_registry():
    return Registry("DB_URL", automigrate_config=LibraryConfig)


def get_application(): ...


app = create_custom_registry().asgi(get_application())
