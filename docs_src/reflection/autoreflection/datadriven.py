import edgy
from edgy.contrib.autoreflection import AutoReflectModel

reflected = edgy.Registry(database="sqlite:///webshopdb.sqlite")


class Product(AutoReflectModel):
    price = edgy.DecimalField(decimal_places=2)
    name = edgy.CharField(max_length=50)

    class Meta:
        registry = reflected
        template = r"{modelname}_{tablename}"


async def main():
    async with reflected:
        print(
            *[
                product.model_dump()
                async for product in reflected.get_model("Product_shoes").query.all()
            ]
        )
        print(
            *[
                product.model_dump()
                async for product in reflected.get_model("Product_trousers").query.all()
            ]
        )
        await reflected.get_model("Product_shoes").query.update(
            price=reflected.get_model("Product_shoes").table.c.price + 10
        )


edgy.run_sync(main())
