from django.core.asgi import get_asgi_application


from edgy import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


application = models.asgi(handle_lifespan=True)(get_asgi_application())
