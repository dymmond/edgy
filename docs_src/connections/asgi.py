from esmerald import Esmerald

from edgy import Registry, Migrate

models = Registry(database="sqlite:///db.sqlite", echo=True)


app = models.asgi(
    Esmerald(
        routes=[...],
    )
)
# monkey-patch app so you can use edgy shell
Migrate(app, models)
