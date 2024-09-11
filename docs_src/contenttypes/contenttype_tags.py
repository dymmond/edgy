import edgy

database = edgy.Database("sqlite:///db.sqlite")
models = edgy.Registry(database=database, with_content_type=True)


class ContentTypeTag(edgy.Model):
    # this prevents the normally set ContentTypeField and replaces it with a common ForeignKey
    content_type = edgy.fields.ForeignKey("ContentType", related_name="tags")
    tag = edgy.fields.TextField()

    class Meta:
        registry = models


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
        await person.content_type.tags.add({"tag": "name=John Doe"})
        await person.content_type.tags.add({"tag": "type=natural_person"})
        org = await Organisation.query.create(name="Edgy org")
        await org.content_type.tags.add({"tag": "name=Edgy org"})
        await org.content_type.tags.add({"tag": "type=organisation"})
        comp = await Company.query.create(name="Edgy inc")
        await comp.content_type.tags.add({"tag": "name=Edgy inc"})
        await comp.content_type.tags.add({"tag": "type=organisation"})
        # now we can query via content_type
        assert await models.content_type.query.filter(tags__tag="type=organisation").count() == 2


edgy.run_sync(main())
