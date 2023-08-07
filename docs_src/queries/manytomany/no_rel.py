import saffier
from saffier import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class Team(saffier.Model):
    name = saffier.CharField(max_length=100)

    class Meta:
        registry = models


class Organisation(saffier.Model):
    ident = saffier.CharField(max_length=100)
    teams = saffier.ManyToManyField(Team)

    class Meta:
        registry = models
