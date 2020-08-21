"""Django views for Codex."""
import logging

from logging import Logger

from django.shortcuts import redirect
from django.shortcuts import render

from . import scanner
from .forms import RootPathForm
from .models import RootPath


LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)


def settings(request):
    rp_id = None
    create_form = None
    bad_update_form = None
    if request.method == "POST":
        instance = None
        action = request.POST["action"]
        if action in ("Delete", "Update"):
            rp_id = request.POST["id"]
            instance = RootPath.objects.get(pk=rp_id)
            if action == "Delete":
                instance.delete()
        if action != "Delete":
            form = RootPathForm(request.POST, instance=instance)
            if form.is_valid():
                data = form.cleaned_data
                if action in ("Add", "Update"):
                    form.save()
                elif action == "Scan":
                    scanner.scan_root(data["path"])
                    scanner.mark_missing(data["path"])
                elif action == "Scan All Roots":
                    scanner.scan_all()
                else:
                    raise ValueError(f"Invalid action {action}")
            elif action == "Add":
                create_form = form
                print(form.errors)
            elif action == "Update":
                bad_update_form = form
                print(form.errors)

    if not create_form:
        create_form = RootPathForm()
    roots = RootPath.objects.all()
    update_forms = []
    for root in roots:
        if root.id == rp_id and bad_update_form:
            update_form = bad_update_form
        else:
            update_form = RootPathForm(instance=root)
        update_forms.append((update_form, root.last_scan))

    context = {
        "create_form": create_form,
        "update_forms": update_forms,
    }
    return render(request, "codex/settings.html", context)
