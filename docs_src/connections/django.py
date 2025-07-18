from django.core.asgi import get_asgi_application


from edgy import Registry, Instance, monkay

models = Registry(database="sqlite:///db.sqlite", echo=True)


application = models.asgi(handle_lifespan=True)(get_asgi_application())

# load settings
monkay.evaluate_settings(ignore_import_errors=False)
# monkey-patch app so you can use edgy shell
monkay.set_instance(Instance(registry=models, app=application))
