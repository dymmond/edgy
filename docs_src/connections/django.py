from django.core.asgi import get_asgi_application


from edgy import Registry, Instance

models = Registry(database="sqlite:///db.sqlite", echo=True)


application = models.asgi(handle_lifespan=True)(get_asgi_application())

# check if settings are loaded
monkay.evaluate_settings_once(ignore_import_errors=False)
# monkey-patch app so you can use edgy shell
monkay.set_instance(Instance(registry=registry, app=app))
