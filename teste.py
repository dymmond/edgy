# This is an auto-generated Edgy model module. Edgy version `0.5.2`.
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
# Feel free to rename the models, but don't rename tablename values or field names.
# The automatic generated models will be subclassed as `edgy.ReflectModel`.


import edgy 


database = edgy.Database('postgresql+asyncpg://expensesusr:67225BBB@localhost:5432/expensesdb')
registry = edgy.Registry(database=database)


class Alembicversion(edgy.ReflectModel):
    class Meta:
        registry = registry
        tablename = 'alembic_version'

class Users(edgy.ReflectModel):
    class Meta:
        registry = registry
        tablename = 'users'

class Trxcategorys(edgy.ReflectModel):
    class Meta:
        registry = registry
        tablename = 'trxcategorys'

class Transactions(edgy.ReflectModel):
    class Meta:
        registry = registry
        tablename = 'transactions'