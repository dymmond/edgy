# Prefetch Related

What is this thing of **prefetch**? Well, imagine you want to get a record from the database and
at the same time you also want to get the nested models related to that same model as well.

The prefetch does this job for you, in other words, pre-loads the related models.

Django for example has the `prefetch_related` as well and Edgy has a similar approach to the
problem but faces it in a different and more clear way.

The **Edgy** way of doing it its by also calling the `prefetch_related` queryset but passing
[Prefetch](#prefetch) instances and utilising the [related_name](./related-name.md) to do it so.

## Prefetch
