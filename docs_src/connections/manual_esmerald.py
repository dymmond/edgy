from esmerald import Esmerald

from edgy import Registry, Instance, monkay

models = Registry(database="sqlite:///db.sqlite", echo=True)


app = Esmerald(
    routes=[...],
    on_startup=[models.__aenter__],
    on_shutdown=[models.__aexit__],
)
# load settings
monkay.evaluate_settings(ignore_import_errors=False)
# monkey-patch app so you can use edgy shell
monkay.set_instance(Instance(app=app, registry=models))
