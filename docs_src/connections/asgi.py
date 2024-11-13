from esmerald import Esmerald

from edgy import Registry, Instance, monkay

models = Registry(database="sqlite:///db.sqlite", echo=True)


app = models.asgi(
    Esmerald(
        routes=[...],
    )
)
# monkey-patch app so you can use edgy shell
monkay.set_instance(Instance(app=app, registry=registry))
