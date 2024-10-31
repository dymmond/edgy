import edgy
import secrets
from contextlib import suppress


class Computer(edgy.Model):
    token: str = edgy.PasswordField(null=False, default=secrets.token_hex)
    ...


obj = await Computer.query.create()
# now let's compare the token safely
secrets.compare_digest(obj.token, "<token>")
