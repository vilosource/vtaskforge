"""Service layer for user preferences and activity tracking."""

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

from .models import RecentAccess, UserProfile

MAX_RECENT = 20


def record_access(user, resource_type: str, resource_id: str, title: str, status: str = "") -> None:
    """Record that a user accessed a resource. Upsert + trim to MAX_RECENT."""
    if user.is_anonymous:
        return

    if not user.has_usable_password():
        return  # Agent user — don't track

    RecentAccess.objects.update_or_create(
        user=user,
        resource_type=resource_type,
        resource_id=resource_id,
        defaults={
            "resource_title": title[:255],
            "resource_status": status[:30],
        },
    )

    # Trim to most recent MAX_RECENT
    ids_to_keep = list(
        RecentAccess.objects.filter(user=user)
        .order_by("-accessed_at")
        .values_list("id", flat=True)[:MAX_RECENT]
    )
    RecentAccess.objects.filter(user=user).exclude(id__in=ids_to_keep).delete()


def get_or_create_profile(user):
    """Get or create a UserProfile, auto-detecting user_type for new profiles."""
    try:
        return UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        if user.has_usable_password():
            user_type = "human"
        else:
            user_type = "agent"
        return UserProfile.objects.create(user=user, user_type=user_type)


def create_service_account(name):
    """Create a service account user with token and profile. Returns (user, token)."""
    user = User.objects.create_user(username=name)
    token = Token.objects.create(user=user)
    UserProfile.objects.create(user=user, user_type="service")
    return user, token
