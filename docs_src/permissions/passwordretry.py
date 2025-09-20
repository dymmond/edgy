import edgy
from contextlib import suppress
from typing import Self, cast

from passlib.context import CryptContext
from pydantic import ValidationError, model_validator

pwd_context = CryptContext(
    # Replace this list with the hash(es) you wish to support.
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
)


def validate_password_strength(password: str) -> None:
    if len(password) < 10:
        raise ValueError()


class User(edgy.Model):
    name: str = edgy.CharField(max_length=255)
    # derive_fn implies the original password is saved in <field>_original
    password: str = edgy.PasswordField(null=False, derive_fn=pwd_context.hash)
    ...

    @model_validator(mode="after")
    def other_validation_check(self) -> Self:
        if getattr(self, "password_original", None) is None:
            return self
        if self.password_original == "":
            raise ValueError("must not be empty")
        # for demonstration purposes we don't do it in model_validator
        # validate_password_strength(self.password_original)
        return self


async def create_user(name: str, pw1: str, pw2: str) -> tuple[bool, User]:
    user = User(name=name, password=(pw1, pw2))

    try:
        # operate on the non-hashed original
        # for demonstration purposes we don't do it in model_validator
        validate_password_strength(user.password_original)
        return True, cast(User, await user.save())
    except Exception:
        # ooops something went wrong, we want to show the user his password again, unhashed
        user.__dict__["password"] = user.password_original
        return False, user


with suppress(ValidationError):
    # model validator fails
    edgy.run_sync(create_user("edgy", "", ""))

# pw strength fails
success, halfinitialized_model = edgy.run_sync(create_user("edgy", "foobar", "foobar"))

# works
user = edgy.run_sync(
    create_user(
        "edgy",
        halfinitialized_model.password + "12345678",
        halfinitialized_model.password + "12345678",
    )
)

# comparing
pwd_context.verify("pw", user.pw)
