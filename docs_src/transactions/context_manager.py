from esmerald import Request, post
from models import Profile, User
from pydantic import BaseModel, EmailStr
from saffier import Database, Registry

# These settings should be placed somewhere
# Central where it can be accessed anywhere.
database = Database("sqlite:///db.sqlite")
models = Registry(database=database)


class UserIn(BaseModel):
    email: EmailStr


@post("/create", description="Creates a user and associates to a profile.")
async def create_user(data: UserIn, request: Request) -> None:
    # This database insert occurs within a transaction.
    # It will be rolled back by the `RuntimeError`.

    async with database.transaction():
        user = await User.query.create(email=data.email, is_active=True)
        await Profile.query.create(user=user)
        raise RuntimeError()
