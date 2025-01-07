from importlib import import_module

from esmerald import Esmerald


def build_path():
    """
    Builds the path of the project and project root.
    """
    Path(__file__).resolve().parent.parent
    SITE_ROOT = os.path.dirname(os.path.realpath(__file__))

    if SITE_ROOT not in sys.path:
        sys.path.append(SITE_ROOT)
        sys.path.append(os.path.join(SITE_ROOT, "apps"))


def setup():
    # do preparations
    ...


def get_application():
    """
    Encapsulate in methods can be useful for capsulating and delaying imports but is optional.
    """
    build_path()
    setup()

    # import now edgy when the path is set
    import edgy

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
