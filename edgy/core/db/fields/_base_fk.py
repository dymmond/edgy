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

        fields_filtered = {target.pkname: target.fields.get(target.pkname)}
        target.model_fields = fields_filtered
        target.model_rebuild(force=True)
        return target(pk=value)

    def check(self, value: Any) -> Any:
        """
        Runs the checks for the fields being validated.
        """
        return value.pk

    def has_default(self) -> bool:
        """Checks if the field has a default value set"""
        return hasattr(self, "default")
