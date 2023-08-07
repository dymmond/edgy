from esmerald import Esmerald
from saffier import Database, Registry

database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


app = Esmerald(
    routes=[...],
    on_startup=[database.connect],
    on_shutdown=[database.disconnect],
)
