# Bulk operations

Bulk operations are different from normal queryset operations.
They don't adher the embed_parent attribute (so they don't load nested objects) and are not necessarily
complete so they can load nested or not set attributes.

Why? Because they are optimized for performance.
By default this won't matter but if you execute such operations on M2M relationships you might get surprised.


### `BulkOperationModelsIncompatible`

This exception contains an attribute named `instances_and_created` a list with the base models
