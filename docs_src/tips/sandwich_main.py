from importlib import import_module

import edgy
from esmerald import Esmerald


def setup():
    # do preparations
    ...


def get_application():
    setup()
    registry = edgy.Registry(url=...)
    # extensions shouldn't be applied yet
    edgy.monkay.set_instance(edgy.Instance(registry=registry), apply_extensions=False)
    # post loads
    import_module("myproject.models")
    app = Esmerald()
    # now apply the extensions
    edgy.monkay.set_instance(edgy.Instance(registry=registry, app=app))
    return app


application = get_application()
