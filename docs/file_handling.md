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

It is realized via thread-safe reserving an available name which is used after for the file creation and
commiting the file changes only after saving the model instance (direct manipulation is still possible via parameters).

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

However there is also just limited access to transactional file handling.

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

!!! Tip:
    You may want to set null=True to allow the deletion of the file.


#### Parameters

- `storage`: (Default: `default`) The default storage to use with the field.
- `with_size`: (Default: `True`). Enable the size field.
- `with_metadata`: (Default: `True`). Enable the metadata field.
- `with_approval`: (Default: `False`). Enable the approval logic.
- `extract_mime`: (Default: `True`). Save the mime in the metadata field. You can set "approved_only" to only do this for approved files.
- `mime_use_magic`: (Default: `False`). Use the `python-magic` library to get the mime type
- `field_file_class`: Provide a custom FieldFile class.
- `generate_name_fn`: fn(instance (if available), name, file, is_direct_name). Customize the name generation.


#### FieldFile

Internally the changes are tracked via the FieldFile pseudo descriptor. It provides some useful interface parts of a file-like (at least
so much, that pillow open is supported).

You can manipulate the file via setting a file-like object or None or for better control, there are three methods:

* save(content, *, name="", delete_old=True, approved=None, storage=None, overwrite=None):
* delete(*, instant, approved): Stage file deletion. When setting instant, the file is deleted without staging.
* set_approved(bool): Set the approved flag. Saved in db with `with_approval`


!!! Tip:
    You can overwrite a file by providing overwrite=True to save and pass the old file name.

!!! Tip:
    You can set the approved flag while saving deleting by providing the approved flag.

### ImageField

Extended FileField for image handling. Because some image formats are notorious unsafe you can limit the loaded formats.

Metadata contains dimensions (width and height).


#### Extra-Parameters

- `with_approval`: (Default: `True`). Enable the approval logic. Enabled by default in ImageFields.
- `image_formats`: (Default: []). Pillow formats to allow loading when the file is not approved. Set to None to allow all.
- `approved_image_formats`: (Default: None). Extra pillow formats to allow loading when the file is not approved. Set to None to allow all (Default).

#### ImageFieldFile

This is a subclass from FieldFile with an additional method

`open_image`

which opens the file as a PIL ImageFile.

!!! Note
    `open_image` honors the format restrictions by the ImageField.



## Concepts

### Size

For easy quota calculations, file sizes are written to a size field. This is enabled by default but can be disabled.


### Metadata

Because metadata of files are highly domain specific a JSONField is used to hold the attributes. By default
`mime` is set and in case of ImageField `height` and `width`. This field is writable, so it can be extended via automatically set metadata.
However when saving a file or the model without exclusions it is overwritten.

The recommend way of extending it is via subclassing the Field and providing a custom extract_metadata.


### Approval concept

FileFields and ImageField have a parameter `with_approval`. This parameter enables a per file approval.
Non-approved files cannot be opened and only a limited set of attributes is extracted (e.g. mime).
