from esmerald import Esmerald

from edgy import Registry

models = Registry(database="sqlite:///db.sqlite", echo=True)


app = models.asgi(
    Esmerald(
        routes=[...],
    )
)
