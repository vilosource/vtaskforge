"""TDD tests for UserProfile.user_type and get_or_create_profile service.

Phase 1 of User Management: formalize agent vs human distinction.
"""

import pytest
from django.contrib.auth.models import User

from prefs.models import UserProfile
from prefs.services import get_or_create_profile


@pytest.mark.django_db
class TestUserProfileUserType:
    def test_profile_user_type_defaults_to_human(self):
        user = User.objects.create_user("human1", password="pass")
        profile = UserProfile.objects.create(user=user)
        assert profile.user_type == "human"

    def test_profile_user_type_agent_settable(self):
        user = User.objects.create_user("agent1")
        profile = UserProfile.objects.create(user=user, user_type="agent")
        assert profile.user_type == "agent"

    def test_profile_user_type_service_settable(self):
        user = User.objects.create_user("svc1")
        profile = UserProfile.objects.create(user=user, user_type="service")
        assert profile.user_type == "service"


@pytest.mark.django_db
class TestGetOrCreateProfile:
    def test_creates_profile_on_first_access(self):
        user = User.objects.create_user("new1", password="pass")
        assert not UserProfile.objects.filter(user=user).exists()
        profile = get_or_create_profile(user)
        assert profile.pk is not None
        assert profile.user == user

    def test_returns_existing_profile(self):
        user = User.objects.create_user("existing1", password="pass")
        existing = UserProfile.objects.create(user=user, user_type="human")
        profile = get_or_create_profile(user)
        assert profile.pk == existing.pk

    def test_auto_detects_human_for_password_user(self):
        user = User.objects.create_user("human2", password="pass")
        profile = get_or_create_profile(user)
        assert profile.user_type == "human"

    def test_auto_detects_agent_for_no_password_user(self):
        user = User.objects.create_user("agent2")  # No password = agent
        profile = get_or_create_profile(user)
        assert profile.user_type == "agent"

    def test_does_not_overwrite_existing_user_type(self):
        """If a profile already has a user_type, don't change it."""
        user = User.objects.create_user("svc2")
        UserProfile.objects.create(user=user, user_type="service")
        profile = get_or_create_profile(user)
        assert profile.user_type == "service"
