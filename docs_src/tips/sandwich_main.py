from importlib import import_module

from ravyn import Ravyn


def build_path():
    """
    Builds the path of the project and project root.
    """
    Path(__file__).resolve().parent.parent
    SITE_ROOT = os.path.dirname(os.path.realpath(__file__))

    if SITE_ROOT not in sys.path:
        sys.path.append(SITE_ROOT)
        sys.path.append(os.path.join(SITE_ROOT, "apps"))


def get_application():
    """
    Encapsulating in methods can be useful for controlling the import order but is optional.
    """
    build_path()
    # import now edgy when the path is set
    import edgy

    registry = edgy.Registry(url=...)
    # extensions shouldn't be applied yet
    edgy.monkay.set_instance(edgy.Instance(registry=registry), apply_extensions=False)
    # load extensions and preloads
    # not evaluate_settings because maybe some preloads weren't resolved
    monkay.evaluate_settings(on_conflict="keep")
    app = Ravyn()
    # now apply the extensions
    edgy.monkay.set_instance(edgy.Instance(registry=registry, app=app))
    return app


application = get_application()
