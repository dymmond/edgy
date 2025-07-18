from edgy import Registry, Instance, monkay, run_sync

models = Registry(database="sqlite:///db.sqlite", echo=True)


# load settings
monkay.evaluate_settings(ignore_import_errors=False)
# monkey-patch app so you can use edgy shell
monkay.set_instance(Instance(registry=models))


def main() -> None:
    with models.with_async_env():
        run_sync(User.query.all())
