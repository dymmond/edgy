from edgy import Registry, Instance, monkay

models = Registry(database="sqlite:///db.sqlite", echo=True)


async def main():
    # load settings
    monkay.evaluate_settings(ignore_import_errors=False)
    # monkey-patch app so you can use edgy shell
    monkay.set_instance(Instance(app=app, registry=registry))
    await models.__aenter__()
    try:
        ...
    finally:
        await models.__aexit__()
