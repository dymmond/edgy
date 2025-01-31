from edgy import Registry, Instance, monkay

models = Registry(database="sqlite:///db.sqlite", echo=True)


# check if settings are loaded
monkay.evaluate_settings(ignore_import_errors=False)
# monkey-patch app so you can use edgy shell
monkay.set_instance(Instance(registry=registry))


def main():
    with models.with_async_env():
        edgy.run_sync(User.query.all())
