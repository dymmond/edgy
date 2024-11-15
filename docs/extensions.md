# Extensions

Edgy has extension support build on the Monkay extensions system. Adding extensions
is possible in settings via the attribute/parameter `extensions`.

They must implement the monkay extension protocol or return as a callable a class implementing the extension protocol.
This sounds hard but it isn't:

``` python
{!> ../docs_src/extensions/settings !}
```

You can also lazily provide them via add_extension (should happen before the instance is set)


``` python
{!> ../docs_src/extensions/add_extension !}
```
