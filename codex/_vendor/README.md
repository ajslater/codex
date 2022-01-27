# Vendored Distributions

## django-haystack

v3.1.1 does not support Django 4.0

### Patches

- The `patch_imports.sh` script takes care of internal haystack references.
- haystack/**init**.py
  - hardcode `__version__`
  - comment out `default_app_config`
- haystack/app.py: `HaystackConfig.name`, `signal_processor_path` getatrr default
- haystack/admin.py: `ungettext` ==> `ngettext`

- xapian-haystack depends on the 'haystack' name so I monkeypatch sys.modules in codex/asgi.py
