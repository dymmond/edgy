from django.core.asgi import get_asgi_application


from edgy import Registry

models = Registry(database="sqlite:///db.sqlite", echo=True)


application = models.asgi(handle_lifespan=True)(get_asgi_application())
