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
        callback=lambda field, context, parameters: f"user-{field.get_callcount()}"
    )


user_model_instance = UserFactory().build()
assert user_model_instance.name == "user-1"
user_model_instance = UserFactory().build()
assert user_model_instance.name == "user-2"
# reset
UserFactory.meta.callcounts.clear()

user_model_instance = UserFactory().build()
assert user_model_instance.name == "user-1"

# provide a different callcounts dict
user_model_instance = UserFactory().build(callcounts={})
assert user_model_instance.name == "user-1"
