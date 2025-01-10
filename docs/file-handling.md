# File handling

File handling is notorios difficult topic in ORMs. In edgy we try to streamline it,
so it is easy to understand and secure.

For this edgy has three security layers:

1. Restricting the image formats parsed (ImageFields).
2. Approved-only open of files (option).
3. Direct size access as field. This way quota handling gets easy. No need to manually track the sizes.
   However this configurable.

and to align it with ORMs it uses a staging+non-overwrite by default concept for more safety.

This means, there has no worry about file names clashing (one of the main reasons people wanting
access to the model instance during file name creation).
Nor that if a file shall be overwritten and the save process fails the file is still overwritten.

It is realized via process pid prefixing and a thread-safe reserving an available name which is used after for the file creation and
commiting the file changes only after saving the model instance (direct manipulation is still possible via parameters).

In short: Just use and stop worrying about the files beeing overwritten. No matter if you use processes or threads.


There are three relevant File classes:

- File: Raw IO to a file-like. Baseclass with many helper functions.
- ContentFile: In-memory IO. Transforms bytes on the fly. But can also be used with files.
- FieldFile: Transactional handler for field oeprations. Used in FileField. Not used directly except in subclasses of FileField.


## Configuration

Filehandling is configured via the global settings. See `edgy/conf/global_settings.py` for the options.

## Direct

Direct access is possible via the storages object in edgy.files. Here you can access the files directly with a storage of your choice.
You get an url or path for accessing the files directly.
This way besides the global configuration nothing is affected.

However there is also just limited access to transactional file handling. There is more control by using `save` explicit.

## Fields

The recommended way to handle files with database tables are FileFields and ImageFields. Both are quite similar,
in fact ImageFields are a subclass with image related extensions.

Fields follow a multi-store concept. It is possible to use in the same FileField multiple stores. The store name is saved along with
the file name, so the right store can be retrieved later.

### FileField

FileField allow to save files next to the database. In contrast to Django, you don't have to worry about the file-handling.
It is all done automatically.

The cleanups when a file gets unreferenced are done automatically (No old files laying around) but this is configurable too.
Queries are fully integrated, it is possible to use delete, bulk_create, bulk_update without problems.

Also by default overwriting is not possible. Files even honor a failed save and doesn't overwrite blindly the old ones.

Setting a file field to None, implicitly deletes the file after saving.

For higher control, the methods of the FieldFile can be used.

!!! Tip
    You may want to set null=True to allow the deletion of the file and having a consistent state afterward.
    However you can circumvent the logic by using `delete` with `instant=True` which disables the transactional
    file handling and just deletes the file and set the name when `null=True` to None.
    In DB the old name will be still referenced, so using `instant=True` is unsafe, except if the object is deleted anyway.
    The `instant` parameter is used for the object deletion hook to cleanup.

#### Parameters

- `storage`: (Default: `default`) The default storage to use with the field.
- `with_size`: (Default: `True`). Enable the size field.
- `with_metadata`: (Default: `True`). Enable the metadata field.
- `with_approval`: (Default: `False`). Enable the approval logic.
- `extract_mime`: (Default: `True`). Save the mime in the metadata field. You can set "approved_only" to only do this for approved files.
- `mime_use_magic`: (Default: `False`). Use the `python-magic` library to get the mime type
- `field_file_class`: Provide a custom FieldFile class.
- `generate_name_fn`: fn(instance (if available), name, file, is_direct_name). Customize the name generation.
- `multi_process_safe`: (Default: `True`). Prefix name with the current process id by default.

!!! Tip
    If you don't want the process pid prefix you can disable this feature with `multi_process_safe=False`.

!!! Note
    The process pid prefixing has a small limitation: all processes must be in the same process namespace (e.g. docker).
    If two processes share the same pid and are alive, the logic doesn't work but because of the random part a collision will be still unlikely.
    You may want to add an unique container identifier or ip address via the generate_name_fn parameter to the path.

#### FieldFile

Internally the changes are tracked via the FieldFile pseudo descriptor. It provides some useful interface parts of a file-like (at least
so much, that pillow open is supported).

You can manipulate the file via setting a file-like object or None or for better control, there are three methods:

* save(content, *, name="", delete_old=True, multi_process_safe=None, approved=None, storage=None, overwrite=None):
* delete(*, instant, approved): Stage file deletion. When setting instant, the file is deleted without staging.
* set_approved(bool): Set the approved flag. Saved in db with `with_approval`

`content` is the most important parameter. It supports File-Like objects in bytes mode as well as bytes directly as well as File instances.

In contrast to Django the conversion is done automatically.


!!! Tip
    You can overwrite a file by providing overwrite=True to save and pass the old file name.
    There is no extra prefix added from `multi_process_safe` by default (except you set the parameter explicitly `True`), so the overwrite works.

!!! Tip
    You can set the approved flag while saving deleting by providing the approved flag.

!!! Tip
    If you want for whatever reason `multi_process_safe` and `overwrite` together, you have to specify both parameters explicitly.

#### Metadata

The default metadata of a FileField consists of

- `mime`

Additionally if `with_size` is True you can query the size of the file in db via the size field.
It is automatically added with the name `<file_field_name>_size`.


### ImageField

Extended FileField for image handling. Because some image formats are notorious unsafe you can limit the loaded formats.


#### Extra-Parameters

- `with_approval`: (Default: `True`). Enable the approval logic. Enabled by default in ImageFields.
- `image_formats`: (Default: []). Pillow formats to allow loading when the file is not approved. Set to None to allow all.
- `approved_image_formats`: (Default: None). Extra pillow formats to allow loading when the file is approved. Set to None to allow all (Default).

#### ImageFieldFile

This is a subclass from FieldFile with an additional method

`open_image`

which opens the file as a PIL ImageFile.

!!! Note
    `open_image` honors the format restrictions by the ImageField.


#### Metadata

The default metadata of a ImageField consists of

- `mime`
- `height` (if the image could be loaded (needs maybe approval))
- `width` (if the image could be loaded (needs maybe approval))

Also the size is available like in FileField in a seperate field (if enabled).

## Concepts

### Quota

When storing user data, a quota calculation is important to prevent a malicous use as well as billing
the users correctly.

A naive implementation would iterate through the objects and add all sizes, so a storage usage can be determined.

This is inperformant! We have the size field.

Instead of iterating through the objects, we just sum up the sizes in db per table via the sum operator


TODO: Example


### Metadata

Because metadata of files are highly domain specific a JSONField is used to hold the attributes. By default
`mime` is set and in case of ImageField `height` and `width`. This field is writable, so it can be extended via automatically set metadata.
However when saving a file or the model without exclusions it is overwritten.

The recommend way of extending it is via subclassing the fields (actually the factories) and providing a custom extract_metadata.

The column name of the metadata field differs from the field name because of size reasons (long names can lead to violating
column name length limits).

It is available as column `<file_or_image_field_name>_mdata`.


### Approval concept

FileFields and ImageField have a parameter `with_approval`. This parameter enables a per file approval.
Non-approved files cannot be opened and only a limited set of attributes is extracted (e.g. mime).

This ensures dangerous files are not opened automatically but first checked by a moderator or admin before they are processed.
For usability `ImageField` allows to specify image formats which are processed regardless if the file was approved.
By default list of these formats is empty (behavior is off).

Third party applications can scan for the field:

`<file_or_image_field_name>_approved` or the column with name `<file_or_image_field_name>_ok`

to detect if a file was approved.
