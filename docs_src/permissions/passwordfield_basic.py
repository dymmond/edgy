import edgy
import secrets
from contextlib import suppress

hasher = Hasher()


class User(edgy.Model):
    pw: str = edgy.PasswordField(null=False, derive_fn=hasher.derive)
    token: str = edgy.PasswordField(null=False, default=secrets.token_hex)
    ...


# we can check if the pw matches by providing a tuple
with suppress(Exception):
    # oops, doesn't work
    obj = await User.query.create(pw=("foobar", "notfoobar"))
obj = await User.query.create(pw=("foobar", "foobar"))
# now let's check the pw
hasher.compare_pw(obj.pw, "foobar")
# now let's compare the token safely
secrets.compare_digest(obj.token, "<token>")
