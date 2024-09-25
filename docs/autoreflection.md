# Automatic Reflection

Let's reflect reflection:

we can reflect tables from database in a model. The next step is to retrieve the tables
and create reflection models from it.

For doing so we have selections via Pattern Models:

They contain a Meta with the regex attribute and generate via the template string or function a new ReflectionModel:


```python
from edgy.contrib.autoreflection import AutoReflectModel

class Reflected(AutoReflectModel):
    class Meta:
        include_pattern = ".*"  # regex or string, default .*. Matches against the tablename
        exclude_pattern = None  # regex or string, default None (disabled). Matches against the tablename
        template = "{modelname}{tablename}"  # string or function with arguments tablename, modelname, tablekey
        databases = (None,)  # Restrict reflection to databases. None: main database of registry, string extra databases of registry
```

Note: when a reflected model is generated the meta is switched in the copy to a regular MetaInfo.

## Meta parameters

Note: we use the table name not the table key.

What is the difference:

table name: `tablename`
table key: `schema.tablename`

That is because edgy handle schemes a little bit different:

In edgy a model can exist in multiple schemes and the scheme is explicit selected.

### Inclusion & Exclusion patterns

Here we can specify patterns against which a regex is checked. By default the `include_pattern` is set to
`.*` which matches all tablenames and the `exclude_pattern` is disabled.

The `include_pattern` will convert all falsy values to the match all, while the exclude_pattern will be really disabled.

### Template

Can be a function which takes the tablename as parameter and is required to return a string.

Or it can be a format string with the possible parameters:

- tablename: the name of the table
- tablekey: the key (name with scheme) of the table
- modelname: the model name

### Databases

In the registry you specify a main database (which is here None) and via the extra dictionary multiple named databases.
The extra databases can be selected via their name while the main can be selected by `None`.

This controls from which database the models are reflected. This is useful to extract data from other databases and to use it in the main application.
