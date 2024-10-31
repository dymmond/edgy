import edgy
from contextlib import suppress

from passlib.context import CryptContext
from pydantic import ValidationError

pwd_context = CryptContext(
    # Replace this list with the hash(es) you wish to support.
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
)


class User(edgy.Model):
    name: str = edgy.CharField(max_length=255)
    # derive_fn implies the original password is saved in <field>_original
    pw: str = edgy.PasswordField(null=False, derive_fn=pwd_context.hash)
    ...

    @model_validator(mode="after")
    def other_validation_check(self) -> str:
        if getattr(self, "pw_original", None) is not None and self.pw_original == "":
            raise ValueError("must not be empty")
        return self


def validate_password_strength(password: str) -> None:
    if len(password) < 10:
        raise ValueError()


async def create_user(pw1, pw2):
    user = User(name="edgy", pw=(pw1, pw2))

    try:
        # operate on the non-hashed original
        validate_password_strength(user.pw_original)
        return True, await model.save()
    except Exception:
        # ooops something went wrong, we want to show the user his password again, unhashed
        model.__dict__["pw"] = model.pw_original
        return False, model


with suppress(ValidationError):
    # model validator fails
    edgy.run_sync(create_user("", ""))

# pw strength fails
success, halfinitialized_model = edgy.run_sync(create_user("foobar", "foobar"))

# works
user = edgy.run_sync(
    create_user(halfinitialized_model.pw + "12345678", halfinitialized_model.pw + "12345678")
)

# comparing
pwd_context.verify("pw", user.pw)
