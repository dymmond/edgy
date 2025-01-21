from monkay import Monkay

__all__ = ["DatabaseTestClient", "Factory"]


Monkay(
    globals(),
    lazy_imports={
        "Factory": ".factory.Factory",
        "DatabaseTestClient": ".client.DatabaseTestClient",
    },
)
del Monkay
