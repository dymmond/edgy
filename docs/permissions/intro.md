# Permissions

One of the most basic needs in the database world is permission handling. Some approaches work via
database users but this is neither portable nor has the flexibility of users which reside as a normal table.

## Permission scopes

### Users

Users are the main entrypoint in nearly every application. For every user multiple attributes can be checked.

### Groups

Groups can be useful for organizing permissions in sets which can be applied to users. In the Permission template they are optional.

### Model names

Model names are a scope limiter for permssions. Instead of allowing e.g. users to edit everything they can only edit blogs. Like groups they are optional.

### Objects

Even stricter than model names are object related permissions. For this we use a ContentType to represent all possible model objects. Like groups they are optional.

## How to use

Permission models detect automatically which features they have. This is why there are field names which are strictly enforced.

E.g. the field `groups` must be a ManyToMany field which points to `Group` when using groups.

## Quickstart


```python
{!> ../docs_src/permissions/quickstart.py !}
```
