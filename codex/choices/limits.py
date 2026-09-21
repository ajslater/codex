"""
Validation limits shared by the server and the admin client.

Every number here is enforced somewhere on the server. The client used
to re-type them, which is how a minimum-length check ended up comparing
against a store key nobody had mapped (#867), and then a second time in
the change-password dialog. Typing a limit once and generating the
client's copy is what makes that class of bug impossible rather than
merely unlikely.

Emitted to ``frontend/src/choices/limits.json`` by ``choices_to_json.py``
with camelCased keys. A ``(min, max)`` tuple dumps as ``[min, max]``,
which is exactly what Vuetify's ``$intRange`` alias takes as its first
positional argument.

**Keep this module free of Django and comicbox imports.**
``codex.settings`` imports it, so it has to stay importable before the
app registry is ready.
"""

from types import MappingProxyType
from typing import Final

#: Django's ``MinimumLengthValidator`` is the only server-side password
#: enforcement -- no DRF serializer carries ``min_length`` -- so OPTIONS
#: metadata could never expose this. A generated constant is the only
#: transport that can.
PASSWORD_MIN_LENGTH: Final = 4

#: Field widths. Defined here and imported by ``codex.models.base`` so
#: the client can bound an input at the same width the column has.
MAX_PATH_LEN: Final = 4095
MAX_NAME_LEN: Final = 128
MAX_FIELD_LEN: Final = 32

#: Issuer URLs run long (e.g. Authentik's ``/application/o/<slug>/``).
OIDC_URL_MAX_LENGTH: Final = 512

#: Django-owned widths, mirrored for the client. A pytest tripwire
#: asserts each still matches the model field it describes.
USERNAME_MAX_LENGTH: Final = 150
GROUP_NAME_MAX_LENGTH: Final = 150
EMAIL_MAX_LENGTH: Final = 254

#: ``(min, max)`` pairs. The SMTP pair replaces bounds Django derived
#: from the SQLite integer range, which accepted port 0 and port 70000.
SMTP_PORT: Final = (1, 65535)
SMTP_TIMEOUT_SECONDS: Final = (1, 600)

#: Admin-flag integers. Both are stored in a shared ``CharField`` and
#: read back through ``get_admin_flag_int``, which honours "0" and "-1"
#: -- so only a serializer bound can reject them. A saved ``0`` for the
#: page size is a live 500: ``ceil(count / 0)``.
CUSTOM_COVER_MAX_UPLOAD_MB: Final = (1, 2048)
BROWSER_MAX_OBJ_PER_PAGE: Final = (1, 65535)

#: The dump. Keys camelCase on the way out, so the client reads
#: ``LIMITS.passwordMinLength``.
LIMITS = MappingProxyType(
    {
        "password_min_length": PASSWORD_MIN_LENGTH,
        "max_path_len": MAX_PATH_LEN,
        "max_name_len": MAX_NAME_LEN,
        "max_field_len": MAX_FIELD_LEN,
        "oidc_url_max_length": OIDC_URL_MAX_LENGTH,
        "username_max_length": USERNAME_MAX_LENGTH,
        "group_name_max_length": GROUP_NAME_MAX_LENGTH,
        "email_max_length": EMAIL_MAX_LENGTH,
        "smtp_port": SMTP_PORT,
        "smtp_timeout_seconds": SMTP_TIMEOUT_SECONDS,
        "custom_cover_max_upload_mb": CUSTOM_COVER_MAX_UPLOAD_MB,
        "browser_max_obj_per_page": BROWSER_MAX_OBJ_PER_PAGE,
    }
)
