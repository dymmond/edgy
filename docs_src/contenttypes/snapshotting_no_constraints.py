import asyncio
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError
import edgy
from edgy import Database, Registry, run_sync
from edgy.contrib.contenttypes import ContentType as _ContentType

database = Database("sqlite:///db.sqlite")


class ContentType(_ContentType):
    no_constraints = True
    created = edgy.fields.DateTimeField(auto_now_add=True, read_only=False)
    keep_until = edgy.fields.DateTimeField(null=True)

    class Meta:
        abstract = True


models = Registry(database=database, with_content_type=ContentType)


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


class Account(edgy.Model):
    owner = edgy.fields.ForeignKey("ContentType", on_delete="CASCADE")

    class Meta:
        registry = models


class Contract(edgy.Model):
    owner = edgy.fields.ForeignKey("ContentType", on_delete="CASCADE")
    account = edgy.fields.ForeignKey("Account", null=True, on_delete="SET_NULL")

    class Meta:
        registry = models


async def main():
    async with database:
        await models.create_all()
        person = await Person.query.create(first_name="John", last_name="Doe")
        snapshot_datetime = datetime.now()
        keep_until = snapshot_datetime + timedelta(days=50)
        org = await Organisation.query.create(
            name="Edgy org",
        )
        comp = await Company.query.create(
            name="Edgy inc",
        )
        account_person = await Account.query.create(
            owner=person.content_type,
            content_type={"created": snapshot_datetime, "keep_until": keep_until},
        )
        account_org = await Account.query.create(
            owner=org.content_type,
            content_type={"created": snapshot_datetime, "keep_until": keep_until},
            contracts_set=[
                {
                    "owner": org.content_type,
                    "content_type": {"created": snapshot_datetime, "keep_until": keep_until},
                }
            ],
        )
        account_comp = await Account.query.create(
            owner=comp.content_type,
            content_type={"created": snapshot_datetime, "keep_until": keep_until},
            contracts_set=[
                {
                    "owner": comp.content_type,
                    "content_type": {"created": snapshot_datetime},
                }
            ],
        )

        # delete old data
        print(
            "deletions:",
            await models.content_type.query.filter(keep_until__lte=keep_until).delete(),
        )
        print("Remaining accounts:", await Account.query.count())  # should be 3
        print("Remaining contracts:", await Contract.query.count())  # should be 2


edgy.run_sync(main())
