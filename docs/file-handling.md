# File Handling

File handling in ORMs is notoriously challenging. Edgy aims to simplify and secure this process.

Edgy implements three security layers:

1.  **Restricting Image Formats:** For `ImageFields`, Edgy restricts the image formats that can be parsed, mitigating potential security vulnerabilities.
2.  **Approved-Only File Opening:** Edgy provides an option for approved-only file opening, ensuring that potentially dangerous files are not automatically processed.
3.  **Direct Size Access:** Edgy offers direct size access as a field, simplifying quota management and eliminating the need for manual size tracking. This feature is configurable.

To align with ORM best practices, Edgy employs a staging and non-overwrite concept for enhanced safety. This prevents file name clashes and ensures that files are not overwritten if the save process fails.

Edgy uses process PID prefixing and thread-safe name reservation, committing file changes only after saving the model instance. This eliminates concerns about file overwrites, regardless of whether you're using processes or threads.

Edgy provides three relevant file classes:

* **File:** A base class for raw I/O operations on file-like objects, offering various helper functions.
* **ContentFile:** An in-memory I/O class that transforms bytes on the fly and can also be used with files.
* **FieldFile:** A transactional handler for field operations, used in `FileField` and its subclasses.

## Configuration

File handling is configured through global settings, which can be found in `edgy/conf/global_settings.py`.

## Direct Access

Direct file access is possible through the `storages` object in `edgy.files`. This allows you to access files directly using a storage of your choice, obtaining URLs or paths for direct file access. This approach minimizes the impact on other parts of your application.

However, direct access provides limited transactional file handling. For more control, use the `save` method explicitly.

## Fields

`FileFields` and `ImageFields` are the recommended way to handle files within database tables. `ImageFields` are a subclass of `FileFields` with additional image-related extensions.

Edgy fields support a multi-store concept, allowing you to use multiple storage backends within the same field. The storage name is saved alongside the file name, enabling retrieval of the correct storage later.

### FileField

`FileField` allows you to save files alongside your database records. Edgy handles file operations automatically, including cleanups when files are unreferenced.

Edgy also prevents overwriting files by default, even in the event of failed save operations.

Setting a `FileField` to `None` implicitly deletes the file after saving.

For finer control, you can use the methods of the `FieldFile` class.

!!! Tip
    Set `null=True` to allow file deletion and maintain a consistent state. Use `delete(instant=True)` to bypass transactional file handling and delete files immediately (use with caution).

#### Parameters

* `storage`: (Default: `default`) The default storage to use.
* `with_size`: (Default: `True`) Enable the size field.
* `with_metadata`: (Default: `True`) Enable the metadata field.
* `with_approval`: (Default: `False`) Enable approval logic.
* `extract_mime`: (Default: `True`) Save MIME type in metadata. Set to `"approved_only"` to do this only for approved files.
* `mime_use_magic`: (Default: `False`) Use the `python-magic` library to get the MIME type.
* `field_file_class`: Provide a custom `FieldFile` class.
* `generate_name_fn`: Customize name generation.
* `multi_process_safe`: (Default: `True`) Prefix name with process ID.

!!! Tip
    Disable process PID prefixing with `multi_process_safe=False`.

!!! Note
    Process PID prefixing requires all processes to be in the same process namespace. Use `generate_name_fn` to add unique identifiers.

#### FieldFile

`FieldFile` tracks changes and provides a file-like interface.

You can manipulate files by setting a file-like object or `None`, or use the following methods:

* `save(content, *, name="", delete_old=True, multi_process_safe=None, approved=None, storage=None, overwrite=None)`: Save a file.
* `delete(*, instant, approved)`: Stage file deletion.
* `set_approved(bool)`: Set the approved flag.

`content` supports file-like objects, bytes, and `File` instances.

!!! Tip
    Overwrite files with `overwrite=True` and the old file name.

!!! Tip
    Set the approved flag during save or delete.

!!! Tip
    Use `multi_process_safe` and `overwrite` together by specifying both parameters explicitly.

#### Metadata

`FileField` metadata includes:

* `mime`

If `with_size` is `True`, the file size is available in the database as `<file_field_name>_size`.

### ImageField

`ImageField` extends `FileField` for image handling, allowing you to restrict loaded image formats.

#### Extra Parameters

* `with_approval`: (Default: `True`) Enable approval logic.
* `image_formats`: (Default: `[]`) Allowed Pillow formats for non-approved files.
* `approved_image_formats`: (Default: `None`) Allowed Pillow formats for approved files.

#### ImageFieldFile

`ImageFieldFile` is a subclass of `FieldFile` with an additional method:

* `open_image`: Opens the file as a PIL `ImageFile`.

!!! Note
    `open_image` honors the format restrictions specified by `ImageField`.

#### Metadata

`ImageField` metadata includes:

* `mime`
* `height`
* `width`

The file size is also available, similar to `FileField`.

## Concepts

### Quota

Use the size field to calculate storage usage efficiently.

```python
{!> ../docs_src/fields/files/file_with_size.py !}
```

### Metadata

Metadata is stored in a `JSONField`. Extend metadata by subclassing fields and providing a custom `extract_metadata` method.

The metadata column is named `<file_or_image_field_name>_mdata`.

### Approval Concept

The `with_approval` parameter enables per-file approval. Non-approved files have limited attribute extraction.

`ImageField` allows specifying image formats that are processed regardless of approval.

Third-party applications can check the `<file_or_image_field_name>_approved` field or `<file_or_image_field_name>_ok` column to determine file approval status.
