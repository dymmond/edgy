import edgy

models = ...


class Foo(edgy.Model, on_conflict="keep"):
    class Meta:
        registry = models


# or


class Foo2(edgy.Model):
    class Meta:
        registry = False


Foo2.add_to_registry(models, name="Foo", on_conflict="replace")
