from ravyn import Request, post
from models import Profile, User
from pydantic import BaseModel, EmailStr

from edgy import Database, Registry

# These settings should be placed somewhere
# Central where it can be accessed anywhere.
models = Registry(database="sqlite:///db.sqlite", extra={"another": "sqlite:///another.sqlite"})


class UserIn(BaseModel):
    email: EmailStr


@post("/create", description="Creates a user and associates to a profile.")
async def create_user(data: UserIn, request: Request) -> None:
    # This database insert occurs within a transaction.
    # It will be rolled back by force_rollback.

    queryset = User.query.using(database="another")

    async with queryset.transaction(force_rollback=True):
        user = await queryset.create(email=data.email, is_active=True)
        await Profile.query.using(database="another").create(user=user)
