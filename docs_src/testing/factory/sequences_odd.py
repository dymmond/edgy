import edgy
from edgy.testing.factory import ModelFactory, FactoryField

models = edgy.Registry(database=...)


class User(edgy.Model):
    name: str = edgy.CharField(max_length=100)

    class Meta:
        registry = models


class UserFactory(ModelFactory):
    class Meta:
        model = User

    name = FactoryField(
        callback=lambda field, context, parameters: f"user-{field.inc_callcount()}"
    )


# manipulate the callcounter. Requires callcounts argument as no context is available here
UserFactory.meta.fields["name"].inc_callcount(amount=-1, callcounts=UserFactory.meta.callcounts)
user_model_instance = UserFactory().build()
assert user_model_instance.name == "user-1"
user_model_instance = UserFactory().build()
assert user_model_instance.name == "user-3"
