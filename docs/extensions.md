# Edgy Extensions

Edgy's architecture includes built-in support for extensions, leveraging the Monkay extensions system. This allows you to enhance Edgy's functionality and customize its behavior to suit your specific needs.

## Adding Extensions

You can add extensions to Edgy through the `extensions` attribute or parameter in your Edgy settings.

Extensions must adhere to the Monkay extension protocol or be a callable that returns a class implementing this protocol.

This might sound complex, but it's designed to be straightforward.

```python
{!> ../docs_src/extensions/settings.py !}
```

**Explanation:**

* **`extensions`:** This attribute or parameter in your Edgy settings is used to specify the extensions you want to load.
* **`MyExtension`:** This class represents your custom extension. It must implement the Monkay extension protocol, which defines how extensions interact with Edgy.
* By adding `MyExtension` to the `extensions` list, you're telling Edgy to load and activate this extension.

## Lazy Loading Extensions

In some cases, you might want to add extensions lazily, after your settings have been defined but before the Edgy instance is fully initialized. You can achieve this using the `add_extension` method.

```python
{!> ../docs_src/extensions/add_extension.py !}
```

**Explanation:**

* **`add_extension`:** This method allows you to add extensions dynamically.
* **`MyExtension`:** This is your custom extension class, which must implement the Monkay extension protocol.
* Calling `add_extension` adds the extension to the list of extensions to be loaded.

**Important Considerations:**

* **Timing:** Ensure that you call `add_extension` before the Edgy instance is fully initialized. Adding extensions after initialization might lead to unexpected behavior.
* **Monkay Protocol:** Your extensions must adhere to the Monkay extension protocol. This protocol defines the methods and attributes that your extensions must implement to interact with Edgy.

## Benefits of Using Extensions

* **Customization:** Extensions allow you to customize Edgy's behavior to meet your specific requirements.
* **Modularity:** Extensions promote modularity by allowing you to separate concerns and add functionality without modifying Edgy's core code.
* **Reusability:** Extensions can be reused across multiple Edgy projects.

## Use Cases

* **Adding custom fields:** You can create extensions that add new field types to Edgy.
* **Implementing custom query logic:** You can create extensions that modify or extend Edgy's query capabilities.
* **Integrating with external services:** You can create extensions that integrate Edgy with external services, such as logging or monitoring tools.
* **Adding custom validation logic:** You can create extensions that add custom validation logic to your Edgy models.

By leveraging Edgy's extension system, you can tailor Edgy to your specific needs and build powerful, customized applications.
