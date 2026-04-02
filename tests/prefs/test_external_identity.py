"""TDD tests for ExternalIdentity model.

Phase 2 of User Management: external channel identity mapping.
"""

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError

from prefs.models import ExternalIdentity


@pytest.mark.django_db
class TestExternalIdentity:
    def test_create_external_identity(self):
        user = User.objects.create_user("human1", password="pass")
        identity = ExternalIdentity.objects.create(
            user=user, provider="slack", external_id="U12345"
        )
        assert identity.pk is not None
        assert identity.provider == "slack"
        assert identity.external_id == "U12345"

    def test_unique_constraint_provider_external_id(self):
        user1 = User.objects.create_user("user1", password="pass")
        user2 = User.objects.create_user("user2", password="pass")
        ExternalIdentity.objects.create(
            user=user1, provider="slack", external_id="U12345"
        )
        with pytest.raises(IntegrityError):
            ExternalIdentity.objects.create(
                user=user2, provider="slack", external_id="U12345"
            )

    def test_lookup_by_provider_and_external_id(self):
        user = User.objects.create_user("human2", password="pass")
        ExternalIdentity.objects.create(
            user=user, provider="slack", external_id="U99999"
        )
        found = ExternalIdentity.objects.get(provider="slack", external_id="U99999")
        assert found.user == user

    def test_user_can_have_multiple_identities(self):
        user = User.objects.create_user("multi1", password="pass")
        ExternalIdentity.objects.create(
            user=user, provider="slack", external_id="U111"
        )
        ExternalIdentity.objects.create(
            user=user, provider="whatsapp", external_id="+358123"
        )
        assert ExternalIdentity.objects.filter(user=user).count() == 2

    def test_delete_user_cascades_identities(self):
        user = User.objects.create_user("cascade1", password="pass")
        ExternalIdentity.objects.create(
            user=user, provider="slack", external_id="U222"
        )
        user.delete()
        assert ExternalIdentity.objects.filter(external_id="U222").count() == 0
