"""
Fold every inbound API credential into scoped ``UserApiKey`` rows.

* Each DRF ``authtoken_token`` row becomes a ``universal`` key named
  "Universal Token", so an existing token keeps logging in everywhere until
  it is revoked. Then the table and its migration records are dropped:
  ``rest_framework.authtoken`` is no longer installed.
* The plaintext Stats API key in the ``AK`` admin flag becomes a hashed
  ``stats`` key owned by the first admin, and the flag row goes. Startup
  deletes rows whose key left the enum, so this has to copy it first.

The digest functions are inlined so later model changes cannot alter what
this migration wrote. The reverse is lossy by design: it deletes every key
that is not a device key, and does not rebuild the token table.
"""

import hashlib
from typing import Final

from django.db import migrations, models

_TOKEN_TABLE: Final = "authtoken_token"  # noqa: S105
_UNIVERSAL: Final = "universal"
_STATS: Final = "stats"
_UNIVERSAL_KEY_NAME: Final = "Universal Token"
_STATS_KEY_NAME: Final = "Stats Key"
_API_KEY_FLAG: Final = "AK"
_PREFIX_LENGTH: Final = 4


def _sha256(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def _md5(secret: str) -> str:
    return hashlib.md5(secret.encode(), usedforsecurity=False).hexdigest()


def _add_key(api_key_model, user_id: int, base_name: str, scope: str, secret: str):
    """Hash ``secret`` into a key row, suffixing the name on a clash."""
    digest = _sha256(secret)
    if api_key_model.objects.filter(digest=digest).exists():
        return
    taken = set(
        api_key_model.objects.filter(user_id=user_id).values_list("name", flat=True)
    )
    name = base_name
    suffix = 2
    while name in taken:
        name = f"{base_name} ({suffix})"
        suffix += 1
    api_key_model.objects.create(
        user_id=user_id,
        name=name,
        scope=scope,
        prefix=secret[:_PREFIX_LENGTH],
        digest=digest,
        kosync_digest=_md5(secret),
    )


def _migrate_tokens(api_key_model, schema_editor) -> None:
    """Copy each DRF token to a universal key, then drop the token table."""
    connection = schema_editor.connection
    if _TOKEN_TABLE not in connection.introspection.table_names():
        return
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT key, user_id FROM {_TOKEN_TABLE} ORDER BY user_id")  # noqa: S608
        rows = cursor.fetchall()
    for secret, user_id in rows:
        if secret:
            _add_key(api_key_model, user_id, _UNIVERSAL_KEY_NAME, _UNIVERSAL, secret)
    schema_editor.execute(f"DROP TABLE IF EXISTS {_TOKEN_TABLE}")
    schema_editor.execute("DELETE FROM django_migrations WHERE app = 'authtoken'")


def _first_admin(user_model):
    """Return the lowest-pk active superuser, else active staff, else None."""
    for role in ("is_superuser", "is_staff"):
        user = (
            user_model.objects.filter(is_active=True, **{role: True})
            .order_by("pk")
            .first()
        )
        if user:
            return user
    return None


def _migrate_stats_key(apps, api_key_model) -> None:
    """Copy the ``AK`` flag's key to the first admin's stats key."""
    flags = apps.get_model("codex", "AdminFlag").objects.filter(key=_API_KEY_FLAG)
    secret = next((flag.value for flag in flags if flag.value), "")
    if secret and (owner := _first_admin(apps.get_model("auth", "User"))):
        _add_key(api_key_model, owner.pk, _STATS_KEY_NAME, _STATS, secret)
    flags.delete()


def _forward(apps, schema_editor) -> None:
    api_key_model = apps.get_model("codex", "UserApiKey")
    _migrate_tokens(api_key_model, schema_editor)
    _migrate_stats_key(apps, api_key_model)


def _reverse(apps, _schema_editor) -> None:
    """Delete the keys the old schema has no column to tell apart."""
    apps.get_model("codex", "UserApiKey").objects.exclude(scope="device").delete()


class Migration(migrations.Migration):
    """Add UserApiKey.scope and migrate tokens and the Stats API key into it."""

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("codex", "0062_device_keys"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="userapikey",
            options={"get_latest_by": "updated_at", "verbose_name": "API key"},
        ),
        migrations.AddField(
            model_name="userapikey",
            name="scope",
            field=models.CharField(
                choices=[
                    ("device", "Device"),
                    ("universal", "Universal"),
                    ("stats", "Stats"),
                ],
                default="device",
                max_length=9,
            ),
        ),
        migrations.RunPython(_forward, _reverse),
        migrations.AlterField(
            model_name="adminflag",
            name="key",
            field=models.CharField(
                choices=[
                    ("AA", "Anonymous User Age Rating"),
                    ("AR", "Age Rating Default"),
                    ("AU", "Auto Update"),
                    ("BT", "Banner Text"),
                    ("CM", "Custom Cover Max Upload Mb"),
                    ("FV", "Folder View"),
                    ("IM", "Import Metadata"),
                    ("KS", "Koreader Sync"),
                    ("LI", "Lazy Import Metadata"),
                    ("MP", "Browser Max Obj Per Page"),
                    ("NU", "Non Users"),
                    ("OP", "Opds"),
                    ("RG", "Registration"),
                    ("RV", "Register Verification"),
                    ("SA", "Stats Api"),
                    ("ST", "Send Telemetry"),
                ],
                db_index=True,
                max_length=2,
            ),
        ),
    ]
