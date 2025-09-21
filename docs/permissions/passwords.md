# Passwords & Tokens

Next to permissions passwords & tokens are essential to restrict the access of users.
For such patterns there is a primititive named PasswordField.

## PasswordField

We have a field named [PasswordField](../fields/index.md#passwordfield). It contains an interfacing
parameter for a password hasher named `derive_fn`, which mangles a user provided password.

```python
{!> ../docs_src/permissions/passwordfield_basic.py !}
```

As also seen in the example when not providing a derive_fn the password is not mangled. This is quite
useful for tokens.

By default the PasswordFields are secret and are hidden when using `exclude_secrets`. You can overwrite the behavior by
providing an explicit secret parameter.

## Passwords

### Integration

Despite edgy has no inbuilt password hasher it provides an easy to use interface for the integration of thirdparty libraries
doing password hashing.

Two good libraries are `passlib` (general including argon2) and `argon2-cffi` (only argon2 family).

=== "With argon2-cffi"
    ```python
    {!> ../docs_src/permissions/passwordargon2id.py !}
    ```

=== "With passlib"
    ```python
    {!> ../docs_src/permissions/passwordpasslib.py !}
    ```


### Validation during creation

A common pattern is to check if the user is able to provide the password 2 times.
This can be automatized via providing a tuple of two string elements.
If they match the check is assumed to be successful and the password processing is continued otherwise an exception is raised.

Sometimes the password should be checked again before mangling. This can be done via the `<fieldname>_original` attribute.
Despite it is a field it is excluded from serialization and has no column, so the password stays secure.
This field is added by default when providing the `derive_fn` parameter but can be explicitly set via `keep_original`.
There is one limitation: after a successful `load`, `insert` or `update`, this includes a successful save, the pseudo-field is blanked with
None. This means a different flow has to be used:

```python title="Realistic example with password retry"
{!> ../docs_src/permissions/passwordretry.py !}
```

## Tokens

The PasswordField is despite its name quite handy for tokens. The default for secret removes the
token automatically from queries with exclude_secrets set and by providing a callable default it is easy to
autogenerate tokens.

```python
{!> ../docs_src/permissions/passwordfield_token.py !}
```

However tokens should be checked by using a cryptographic safe compare method. Otherwise it
is possible to open a side-channel attack by comparing timings.
