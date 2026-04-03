"""Convert Review.reviewer_id CharField to Review.reviewer FK User.

Phase 0, Step 4: Rename old column, add FK, resolve, drop old.
"""

import logging

from django.db import migrations, models
import django.db.models.deletion

logger = logging.getLogger(__name__)


def resolve_reviewers(apps, schema_editor):
    User = apps.get_model("auth", "User")
    user_map = {u.username: u.pk for u in User.objects.all()}

    from django.db import connections
    cursor = connections[schema_editor.connection.alias].cursor()
    cursor.execute("SELECT id, _old_reviewer_id FROM reviews_review")

    stats = {"resolved": 0, "unresolvable": 0, "empty": 0}
    for row in cursor.fetchall():
        review_id, old_val = row
        if not old_val or old_val.strip() == "":
            stats["empty"] += 1
            continue
        user_pk = user_map.get(old_val)
        if user_pk:
            cursor.execute("UPDATE reviews_review SET reviewer_id = %s WHERE id = %s", [user_pk, review_id])
            stats["resolved"] += 1
        else:
            stats["unresolvable"] += 1
            logger.warning(f"Unresolvable reviewer_id '{old_val}' on review {review_id}")

    logger.info(f"Review reviewer migration: {stats}")


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0001_initial"),
        ("auth", "__first__"),
    ]

    operations = [
        migrations.RenameField(model_name="review", old_name="reviewer_id", new_name="_old_reviewer_id"),
        migrations.AddField(
            model_name="review", name="reviewer",
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reviews", to="auth.user",
            ),
        ),
        migrations.RunPython(resolve_reviewers, reverse_noop),
        migrations.RemoveField(model_name="review", name="_old_reviewer_id"),
    ]
