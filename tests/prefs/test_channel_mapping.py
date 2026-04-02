"""TDD tests for ChannelProjectMapping model.

Phase 3 of User Management: channel-to-project resolution.
"""

import pytest
from django.db import IntegrityError

from prefs.models import ChannelProjectMapping


@pytest.mark.django_db
class TestChannelProjectMapping:
    def test_create_mapping(self):
        mapping = ChannelProjectMapping.objects.create(
            provider="slack", channel_id="C123", channel_name="#vtf-dev",
            project_id="proj1",
        )
        assert mapping.pk is not None

    def test_unique_constraint_provider_channel(self):
        ChannelProjectMapping.objects.create(
            provider="slack", channel_id="C123", project_id="proj1"
        )
        with pytest.raises(IntegrityError):
            ChannelProjectMapping.objects.create(
                provider="slack", channel_id="C123", project_id="proj2"
            )

    def test_lookup_project_by_channel(self):
        ChannelProjectMapping.objects.create(
            provider="slack", channel_id="C999", project_id="my-project"
        )
        mapping = ChannelProjectMapping.objects.get(
            provider="slack", channel_id="C999"
        )
        assert mapping.project_id == "my-project"

    def test_update_mapping(self):
        mapping = ChannelProjectMapping.objects.create(
            provider="slack", channel_id="C123", project_id="old-project"
        )
        mapping.project_id = "new-project"
        mapping.save()
        mapping.refresh_from_db()
        assert mapping.project_id == "new-project"

    def test_delete_mapping(self):
        mapping = ChannelProjectMapping.objects.create(
            provider="slack", channel_id="C123", project_id="proj1"
        )
        mapping.delete()
        assert not ChannelProjectMapping.objects.filter(channel_id="C123").exists()
