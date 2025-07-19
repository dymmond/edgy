from esmerald import Esmerald

from edgy import Registry, Instance, monkay

models = Registry(database="sqlite:///db.sqlite", echo=True)


app = models.asgi(
    Esmerald(
        routes=[...],
    )
)

# load settings
monkay.evaluate_settings(ignore_import_errors=False)
# monkey-patch app so you can use edgy shell
monkay.set_instance(Instance(registry=models, app=app))
