import edgy

database = edgy.Database("sqlite:///db.sqlite")
models = edgy.Registry(database=database, with_content_type=True)


class Person(edgy.Model):
    first_name = edgy.fields.CharField(max_length=100)
    last_name = edgy.fields.CharField(max_length=100)

    class Meta:
        registry = models
        unique_together = [("first_name", "last_name")]


class Organisation(edgy.Model):
    name = edgy.fields.CharField(max_length=100, unique=True)

    class Meta:
        registry = models


class Company(edgy.Model):
    name = edgy.fields.CharField(max_length=100, unique=True)

    class Meta:
        registry = models


async def main():
    async with database:
        await models.create_all()
        person = await Person.query.create(first_name="John", last_name="Doe")
        org = await Organisation.query.create(name="Edgy org")
        comp = await Company.query.create(name="Edgy inc")
        # we all have the content_type attribute and are queryable
        assert await models.content_type.query.count() == 3


edgy.run_sync(main())
