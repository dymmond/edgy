from esmerald import Esmerald

from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


app = models.asgi(
    Esmerald(
        routes=[...],
    )
)
