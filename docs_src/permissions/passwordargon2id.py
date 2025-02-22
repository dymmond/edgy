import edgy

from argon2 import PasswordHasher

hasher = PasswordHasher()


class User(edgy.Model):
    name: str = edgy.CharField(max_length=255)
    # derive_fn implies the original password is saved in <field>_original
    pw: str = edgy.PasswordField(null=False, derive_fn=hasher.hash)
    ...


user = await User.query.create(name="foo", pw="foo")

provided_pw = "foo"
# comparing
if not hasher.verify(provided_pw, user.pw):
    raise

# rehash
if hasher.check_needs_rehash(user.pw):
    user.pw = provided_pw
    await user.save()
