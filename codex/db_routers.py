"""Database routers."""


class SilkRouter:
    """Route django-silk's models to the silky DB; everything else stays on default."""

    SILK_APP = "silk"
    SILK_DB = "silky"
    DEFAULT_DB = "default"

    def db_for_read(self, model, **_hints):
        """Read silk from the silky DB."""
        if model._meta.app_label == self.SILK_APP:
            return self.SILK_DB
        return None

    def db_for_write(self, model, **_hints):
        """Write silk to the silky DB."""
        if model._meta.app_label == self.SILK_APP:
            return self.SILK_DB
        return None

    def allow_relation(self, obj1, obj2, **_hints):
        """Silk never joins to app tables; allow all other relations."""
        silk_apps = {obj1._meta.app_label, obj2._meta.app_label}
        if self.SILK_APP in silk_apps and len(silk_apps) == 2:
            return False
        return None

    def allow_migrate(self, db, app_label, **_hints):
        """Silk migrations only run on the silky DB; everything else only on default."""
        if app_label == self.SILK_APP:
            return db == self.SILK_DB
        return db == self.DEFAULT_DB
