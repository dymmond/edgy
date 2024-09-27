import edgy
from edgy.contrib.autoreflection import AutoReflectModel

registry = edgy.Registry(
    database="sqlite:///newapp.sqlite",
    extra={
        "legacy": "sqlite:///webshopdb.sqlite",
        "ancient": "sqlite:///webshopdb.sqlite",
    },
)


class Product(AutoReflectModel):
    price = edgy.DecimalField(decimal_places=2)
    name = edgy.CharField(max_length=50)

    class Meta:
        registry = registry
        template = r"{modelname}_{tablename}"
        databases = ("legacy",)


class AncientProduct(edgy.ReflectModel):
    price = edgy.DecimalField(decimal_places=2)
    name = edgy.CharField(max_length=50)
    __using_schema__ = None

    class Meta:
        registry = registry
        tablename = "shoes"


AncientProduct.database = registry.extra["ancient"]


async def main():
    async with registry:
        print(*[product.model_dump() async for product in AncientProduct.query.all()])
        print(
            *[
                product.model_dump()
                async for product in registry.get_model("Product_shoes").query.all()
            ]
        )
        print(
            *[
                product.model_dump()
                async for product in registry.get_model("Product_trousers").query.all()
            ]
        )
        await registry.get_model("Product_shoes").query.update(
            price=registry.get_model("Product_shoes").table.c.price + 10
        )


edgy.run_sync(main())
