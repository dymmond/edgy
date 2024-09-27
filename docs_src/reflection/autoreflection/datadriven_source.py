import edgy

registry = edgy.Registry(database="sqlite:///webshopdb.sqlite")


class Trouser(edgy.Model):
    price = edgy.DecimalField(max_digits=2, decimal_places=2)
    name = edgy.CharField(max_length=50)
    with_pocket = edgy.BooleanField()
    size = edgy.IntegerField()

    class Meta:
        registry = registry


class Shoe(edgy.Model):
    price = edgy.DecimalField(decimal_places=2)
    name = edgy.CharField(max_length=50)
    waterproof = edgy.BooleanField()
    size = edgy.FloatField()

    class Meta:
        registry = registry


async def main():
    async with registry:
        await registry.create_all()
        await Trouser.query.create(price=10.50, name="Fancy Jeans", with_pocket=True, size=30)
        await Shoe.query.create(price=14.50, name="SuperEliteWalk", waterproof=False, size=10.5)


edgy.run_sync(main())
