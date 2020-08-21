"""Django views for Codex."""
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import UserPassesTestMixin
from django.forms import modelformset_factory
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.views.generic import DeleteView
from django.views.generic import FormView
from django.views.generic import ListView
from django.views.generic import RedirectView
from django.views.generic import UpdateView

from codex.forms import ScanAllForm
from codex.forms import ScanRootPathForm
from codex.library import scanner
from codex.models import RootPath


LOG = logging.getLogger(__name__)


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_staff


class MarkDeleteView(DeleteView):
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.soft_delete()
        self.object.save()
        return HttpResponseRedirect(self.get_success_url())


class SettingsListView(CreateView, ListView, StaffRequiredMixin):
    template_name = "codex/settings.html"
    model = RootPath
    fields = ["path", "scan_frequency"]
    success_url = reverse_lazy("admin_settings")

    def get_queryset(self):
        return RootPath.objects.all().filter(deleted_at=None)

    def get(self, request, *args, **kwargs):
        # XXX YUCK!
        self.object_list = self.get_queryset()
        self.object = None
        fs_cls = modelformset_factory(RootPath, exclude=["deleted_at"])
        formset = fs_cls(queryset=RootPath.objects.filter(deleted_at=None))
        print(RootPath.objects.filter(deleted_at=None))
        clean_fs = []
        for f in formset:
            f.fields["path"].widget.attrs["readonly"] = True
            f.fields["path"].widget.attrs["disabled"] = True
            f.fields["last_scan"].widget.attrs["readonly"] = True
            f.fields["last_scan"].widget.attrs["disabled"] = True
            print(f.instance.id, f.instance.path)
            if f.instance.id:
                clean_fs.append(f)
        context = self.get_context_data(
            scan_all_form=ScanAllForm(), scan_form=ScanRootPathForm(), formset=clean_fs
        )
        return self.render_to_response(context)


class SettingsUpdateView(UpdateView, StaffRequiredMixin):
    template_name = SettingsListView.template_name
    model = RootPath
    success_url = reverse_lazy("admin_settings")
    fields = ["scan_frequency"]

    def get_object(self, queryset=None):
        queryset = self.get_queryset().filter(deleted_at=None)
        return super().get_object(queryset)

    def post(self, request, *args, **kwargs):
        # XXX THIS IS SUPER GROSS
        for key, val in request.POST.items():
            if key.rfind("scan_frequency"):
                request.POST = {"scan_frequency": val}
                break
        return super().post(request, *args, **kwargs)


class SettingsCreateView(UpdateView, StaffRequiredMixin):
    template_name = SettingsListView.template_name
    model = RootPath
    success_url = reverse_lazy("admin_settings")
    fields = ["path", "scan_frequency"]
    initial = {"deleted_at": None}

    def get_object(self, queryset=None):
        defaults = self.get_initial()
        defaults["path"] = self.request.POST.get("path")
        obj, created = self.model.objects.update_or_create(
            defaults=defaults, path=defaults["path"]
        )
        print(obj, created)
        return obj


class SettingsDeleteView(UpdateView, StaffRequiredMixin):
    template_name = SettingsListView.template_name
    model = RootPath
    success_url = reverse_lazy("admin_settings")
    fields = []

    def form_valid(self, form):
        form.instance.soft_delete()
        return super().form_valid(form)


class SettingsScanView(UpdateView, StaffRequiredMixin):
    success_url = reverse_lazy("admin_settings")
    form_class = ScanRootPathForm
    model = RootPath

    def form_valid(self, form):
        force = form.cleaned_data.get("force", False)
        scanner.scan_root(form.instance, force)
        return super().form_valid(form)


class SettingsScanAllView(FormView, StaffRequiredMixin):
    form_class = ScanAllForm
    success_url = reverse_lazy("admin_settings")

    def form_valid(self, form):
        force = form.cleaned_data.get("force", False)
        scanner.scan_all(force)
        return super().form_valid(form)
