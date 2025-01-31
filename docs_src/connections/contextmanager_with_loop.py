import asyncio
from contextvars import ContextVar
from edgy import Registry, Instance, monkay, run_sync

models = Registry(database="sqlite:///db.sqlite", echo=True)


# multithreading safe
event_loop = ContextVar("event_loop", default=None)


def handle_request():
    loop = event_loop.get()
    if loop is None:
        # eventloops die by default with the thread
        loop = asyncio.new_event_loop()
        event_loop.set(loop)
    with models.with_loop(loop):
        edgy.run_sync(User.query.all())


def get_application():
    app = ...
    # load settings
    monkay.evaluate_settings(ignore_import_errors=False)
    # monkey-patch app so you can use edgy shell
    monkay.set_instance(Instance(registry=registry, app=app))
    return app


app = get_application()
