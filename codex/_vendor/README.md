# Vendored Distributions

## django-haystack

v3.2.1 Leaves zombie processes if the multiprocessing update fails.
If my patch works submit a solution to django-haystack.

### Patches

#### Functional

- management/commands/update.py:373 add a try block to catch multiprocessing pool errors and prevent zombies.

#### Fixing references to codex.\_vendor

- The `patch_imports.sh` script takes care of internal haystack references.
- haystack/\_\_init\_\_.py
  - hardcode `__version__`

- haystack/app.py: `HaystackConfig.name`, `signal_processor_path` getatrr default

- xapian-haystack depends on the 'haystack' name so I monkeypatch sys.modules in codex/asgi.py
