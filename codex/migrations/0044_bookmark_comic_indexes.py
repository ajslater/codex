"""
Comic-leading composite indexes for per-comic bookmark probes.

The UNREAD/READ browse filter now probes "my finished bookmark for this
comic" per comic row (correlated EXISTS). The existing unique_together
index leads with user, and under stale sqlite_stat1 the planner flipped
the probe onto the plain user index — a measured 17s vs 27ms plan.
Comic-first composites dominate both the user and session access paths.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add (comic, user) and (comic, session) indexes to Bookmark."""

    dependencies = [("codex", "0043_comicbox_tagging_defaults")]

    operations = [
        migrations.AddIndex(
            model_name="bookmark",
            index=models.Index(fields=["comic", "user"], name="bookmark_comic_user"),
        ),
        migrations.AddIndex(
            model_name="bookmark",
            index=models.Index(
                fields=["comic", "session"], name="bookmark_comic_session"
            ),
        ),
    ]
