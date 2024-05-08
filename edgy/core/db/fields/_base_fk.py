from typing import Any

from edgy.core.db.fields.base import BaseField


class BaseForeignKey(BaseField):
    @property
    def target(self) -> Any:
        """
        The target of the ForeignKey model.
        """
        if not hasattr(self, "_target"):
            if isinstance(self.to, str):
                self._target = self.registry.models[self.to]  # type: ignore
            else:
                self._target = self.to
        return self._target

    @target.setter
    def target(self, value: Any) -> Any:
        self._target = value

    def get_related_name(self) -> str:
        """
        Returns the name of the related name of the current relationship between the to and target.

        :return: Name of the related_name attribute field.
        """
        return self.related_name

    def expand_relationship(self, value: Any) -> Any:
        target = self.target
        if isinstance(value, target):
            return value

        if not isinstance(value, dict):
            if len(target.proxy_model.pknames) != 1:
                raise
            value = {target.proxy_model.pknames[0]: value}
        fields_filtered = {}
        query = {}
        for pkname, val in value.items():
            fields_filtered[pkname] = target.proxy_model.fields.get(pkname)
            query[pkname] = val
        target.proxy_model.model_fields = fields_filtered
        target.proxy_model.model_rebuild(force=True)
        return target.proxy_model(**query)

    def check(self, value: Any) -> Any:
        """
        Runs the checks for the fields being validated.
        """
        assert len(self.target.pknames) == 1
        return value.pk
