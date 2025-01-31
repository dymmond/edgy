from edgy import Registry, Instance, monkay

models = Registry(database="sqlite:///db.sqlite", echo=True)


async def main():
    # load settings
    monkay.evaluate_settings(ignore_import_errors=False)
    # monkey-patch so you can use edgy shell
    monkay.set_instance(Instance(registry=registry))
    async with models:
        ...
