import edgy

from passlib.context import CryptContext
from pydantic import ValidationError

pwd_context = CryptContext(
    # Replace this list with the hash(es) you wish to support.
    schemes=["argon2", "pbkdf2_sha256"],
    deprecated="auto",
)


class User(edgy.Model):
    name: str = edgy.CharField(max_length=255)
    # derive_fn implies the original password is saved in <field>_original
    pw: str = edgy.PasswordField(null=False, derive_fn=pwd_context.hash)
    ...


user = await User.query.create(name="foo", pw="foo")

provided_pw = "foo"
# comparing
if not pwd_context.verify(provided_pw, user.pw):
    raise


if pwd_context.needs_update(user.pw):
    user.pw = provided_pw
    await user.save()
