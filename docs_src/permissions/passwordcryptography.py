import os
from base64 import b64decode
import re
import edgy

from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

params_matcher = re.compile(r"^\$argon2id\$([^$]+\$[^$]+)\$")

# example argon2id string: '$argon2id$v=19$m=65536,t=1,p=4$OgFOjteCbu56aQyTtgcZag$V8lqOMS8jhg80a5aDCZXP04dkqJUbpS27MsxLPk63GI'


def hashing(inp: str, salt: bytes | None = None) -> str:
    salt = os.urandom(16) if salt is None else salt
    kdf = Argon2id(
        salt=salt,
        length=32,
        iterations=1,
        lanes=4,
        memory_cost=64 * 1024,
    )
    return kdf.derive_phc_encoded(inp.encode("utf8"))


def needs_rehash_v1(old: str, pw: str) -> bool:
    old_splitted = old.split("$", 5)
    if len(old_splitted) != 6 or old_splitted[1] != "argon2id":
        return True
    # proper way
    padding = "=" * (3 - ((len(old_splitted[4]) + 3) % 4))
    salt = b64decode(old_splitted[4] + padding)
    # hacky way, validate=False (default)
    # salt = b64decode(old_splitted[4] + "==")
    return hashing(pw, salt) != old


def needs_rehash_v2(old: str, pw: str) -> bool:
    params_extracted = params_matcher.match(old)
    if params_extracted is None:
        return True
    return params_extracted[1] != params_matcher.match(hashing(pw))[1]  # type: ignore


def needs_rehash_v3(old: str, pw: str) -> bool:
    old_splitted = old.split("$", 5)
    if len(old_splitted) != 6 or old_splitted[1] != "argon2id":
        return True
    return "$".join(hashing(pw).split("$", 5)[:4]) != "$".join(old_splitted[:4])


class User(edgy.Model):
    name: str = edgy.CharField(max_length=255)
    # derive_fn implies the original password is saved in <field>_original
    pw: str = edgy.PasswordField(null=False, derive_fn=hashing)
    ...


user = await User.query.create(name="foo", pw="foo")

provided_pw = "foo"
# comparing
try:
    Argon2id.verify_phc_encoded(provided_pw, user.pw)
except InvalidKey:
    raise

# rehash (either v1, v2, v3)
if needs_rehash_v1(user.pw):
    user.pw = provided_pw
    await user.save()
