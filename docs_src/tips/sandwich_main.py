import edgy
from esmerald import Esmerald


def get_application():
    setup()
    registry = edgy.Registry(url=...)
    # extensions shouldn't applied yet
    edgy.monkay.set_instance(edgy.Instance(registry=registry), apply_extensions=False)
    # post loads
    import_module("myproject.models")
    app = Esmerald()
    # now apply the extensions
    edgy.monkay.set_instance(edgy.Instance(registry=registry, app=app))
    return app
