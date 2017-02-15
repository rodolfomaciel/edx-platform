"""
Models used by the block structure framework.
"""

from django.db import models
from openedx.core.djangoapps.xmodule_django.models import UsageKeyField


class BlockStructure(models.Model):
    """
    Model for storing Block Structure information.
    """
    data_usage_key = UsageKeyField(
        u'Identifier of the data being collected.',
        blank=False,
        max_length=255,
        db_index=True,
    )
    data_version = models.CharField(
        u'Version of the data at the time of collection.',
        blank=True,
        max_length=255,
    )
    data_edit_timestamp = models.DateTimeField(
        u'Edit timestamp of the data at the time of collection.',
        blank=True,
        null=True,
    )

    transformers_schema_version = models.CharField(
        u'Representation of the schema version of the transformers used during collection.',
        blank=False,
        max_length=255,
    )
    block_structure_schema_version = models.CharField(
        u'Version of the block structure schema at the time of collection.',
        blank=False,
        max_length=255,
    )

    collected_data = models.FileField()

    @classmethod
    def get_current(cls, data_usage_key):
        """
        Returns the entry associated with the given data_usage_key.
        """
        return cls.objects.get(data_usage_key=data_usage_key)

    def get_collected_data(self):
        """
        Returns the collected data for this instance.
        """
        return self.collected_data.read()

    @classmethod
    def update_or_create_with_data(cls, collected_content, **kwargs):
        """
        """
        cls.objects.update_or_create(**kwargs)


    def delete(self):
        # TODO override to delete underyling file object also
        pass
