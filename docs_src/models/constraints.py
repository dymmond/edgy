import edgy
import sqlalchemy
from edgy import Database, Registry


database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class User(edgy.Model):
    name = edgy.fields.CharField(max_length=255)
    is_admin = edgy.fields.BooleanField(default=False)
    age = edgy.IntegerField(null=True)

    class Meta:
        registry = models
        constraints = [sqlalchemy.CheckConstraint("age > 13 OR is_admin = true", name="user_age")]
