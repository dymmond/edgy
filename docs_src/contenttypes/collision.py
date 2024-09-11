import asyncio

from sqlalchemy.exc import IntegrityError
import edgy

database = edgy.Database("sqlite:///db.sqlite")
models = edgy.Registry(database=database, with_content_type=True)


class Apple(edgy.Model):
    g = edgy.fields.SmallIntegerField()

    class Meta:
        registry = models


class Pear(edgy.Model):
    g = edgy.fields.SmallIntegerField()

    class Meta:
        registry = models


async def main():
    async with database:
        await models.create_all()
        await Apple.query.bulk_create(
            [{"g": i, "content_type": {"collision_key": str(i)}} for i in range(1, 100, 10)]
        )
        apples = [
            await asyncio.create_task(content_type.get_instance())
            async for content_type in models.content_type.query.filter(name="Apple")
        ]
        try:
            await Pear.query.bulk_create(
                [{"g": i, "content_type": {"collision_key": str(i)}} for i in range(1, 100, 10)]
            )
        except IntegrityError:
            pass
        pears = [
            await asyncio.create_task(content_type.get_instance())
            async for content_type in models.content_type.query.filter(name="Pear")
        ]
        assert len(pears) == 0


edgy.run_sync(main())
