"""Django views for Codex."""
from django.shortcuts import render

from codex import models


def comics(request):
    comics = models.Comic.objects.all()
    context = {"comics": comics}
    return render(request, "codex/comics.html", context)


def comic(request, comic_id):
    comic = models.Comic.objects.get(comic_id)
    context = {"comic": comic}
    return render(request, "codex/comic.html", context)
