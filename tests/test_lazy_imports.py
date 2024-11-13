import edgy


def test_lazy_imports():
    missing = edgy.monkay.find_missing(
        all_var=edgy.__all__,
        search_pathes=[
            # FIXME: false positives because re-exports
            # ".core.connection",
            # ".core.db.models",
            ".core.db.fields",
            ".core.db.constants",
        ],
    )
    missing.pop("edgy.core.db.fields.AutoNowMixin")
    missing.pop("edgy.core.db.fields.BaseField")
    missing.pop("edgy.core.db.fields.BaseFieldType")
    assert not missing
