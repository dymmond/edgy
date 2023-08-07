import saffier
from saffier import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class Organisation(saffier.Model):
    ident = saffier.CharField(max_length=100)

    class Meta:
        registry = models


class Team(saffier.Model):
    org = saffier.ForeignKey(Organisation, on_delete=saffier.RESTRICT)
    name = saffier.CharField(max_length=100)

    class Meta:
        registry = models
