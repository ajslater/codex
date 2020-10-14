"""Frontend views."""
from django.shortcuts import render
from django.urls import get_script_prefix

from codex.settings.settings import DEBUG


def app(request):
    """Serve the main application page."""
    return render(
        request,
        "index.html",
        context={"root_path": get_script_prefix(), "DEBUG": DEBUG},
    )


def webmanifest(request):
    """Serve the webmanifest spec. For android and chrome."""
    return render(request, "site.webmanifest", content_type="application/manifest+json")


def browserconfig(request):
    """Serve browserconfig xml for microsoft."""
    return render(request, "browserconfig.xml", content_type="text/xml")
