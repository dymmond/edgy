# This is an auto-generated Edgy model module. Edgy version `0.5.2`.
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
# Feel free to rename the models, but don't rename tablename values or field names.
# The automatic generated models will be subclassed as `edgy.ReflectModel`.


import edgy
from edgy import Index, UniqueConstraint

database = edgy.Database("postgresql+asyncpg://expensesusr:67225BBB@localhost:5432/expensesdb")
registry = edgy.Registry(database=database)


class Alembicversion(edgy.ReflectModel):
    version_num = edgy.CharField(max_length=32, null=False, primary_key=True)

    class Meta:
        registry = registry
        tablename = "alembic_version"


class Users(edgy.ReflectModel):
    id = edgy.BigIntegerField(null=False, primary_key=True)
    first_name = edgy.CharField(max_length=150, null=False)
    last_name = edgy.CharField(max_length=150, null=False)
    username = edgy.CharField(max_length=150, null=False)
    email = edgy.CharField(max_length=120, null=False)
    password = edgy.CharField(max_length=128, null=False)
    last_login = edgy.DateTimeField(null=True)
    is_active = edgy.BooleanField(null=False)
    is_staff = edgy.BooleanField(null=False)
    is_superuser = edgy.BooleanField(null=False)

    class Meta:
        registry = registry
        tablename = "users"
        unique_together = [
            UniqueConstraint(fields=["email"]),
            UniqueConstraint(fields=["username"]),
        ]


class Trxcategorys(edgy.ReflectModel):
    id = edgy.IntegerField(null=False, primary_key=True)
    description = edgy.CharField(max_length=100, null=False)
    cat_type = edgy.ChoiceField(null=False)
    user = edgy.ForeignKey(
        null=False,
        to="Users",
        on_update="CASCADE",
        on_delete="CASCADE",
        related_name="user_users_set",
    )

    class Meta:
        registry = registry
        tablename = "trxcategorys"


class Transactions(edgy.ReflectModel):
    id = edgy.IntegerField(null=False, primary_key=True)
    trx_type = edgy.ChoiceField(null=False)
    amount = edgy.DecimalField(max_digits=7, decimal_places=2, null=False)
    currency = edgy.CharField(max_length=3, null=False)
    trx_date = edgy.DateTimeField(null=False)
    notes = edgy.CharField(max_length=100, null=False)
    user = edgy.ForeignKey(
        null=False,
        to="Users",
        on_update="CASCADE",
        on_delete="CASCADE",
        related_name="user_users_set",
    )
    category = edgy.ForeignKey(
        null=True,
        to="Trxcategorys",
        on_update="CASCADE",
        on_delete="CASCADE",
        related_name="category_trxcategorys_set",
    )

    class Meta:
        registry = registry
        tablename = "transactions"
        indexes = [
            Index(suffix="idx", max_name_length=30, name="idx_currency", fields=["currency"])
        ]


class Tiago(edgy.ReflectModel):
    id = edgy.BigIntegerField(null=False, primary_key=True)
    name = edgy.CharField(max_length=None, null=False)
    email = edgy.CharField(max_length=None, null=False)

    class Meta:
        registry = registry
        tablename = "tiago"
        unique_together = [UniqueConstraint(fields=["name", "email"])]
