import asyncio
from edgy import Registry, Instance, monkay, run_sync

models = Registry(database="sqlite:///db.sqlite", echo=True)

# load settings
monkay.evaluate_settings(ignore_import_errors=False)
# monkey-patch app so you can use edgy shell
monkay.set_instance(Instance(registry=registry))

loop = asyncio.new_event_loop()
with models.with_loop(loop):
    edgy.run_sync(User.query.all())

# uses the same loop
with models.with_loop(loop):
    edgy.run_sync(User.query.all())


loop.run_until_complete(loop.shutdown_asyncgens())
loop.close()
