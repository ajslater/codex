"""Download a group of comics in a zipfile."""

from django.http import HttpResponseBadRequest
from django.http.response import FileResponse, Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from loguru import logger
from typing_extensions import override
from zipstream import ZipStream

from codex.views.browser.filters.filter import BrowserFilterView


class GroupDownloadView(BrowserFilterView):
    """Return a group of comic archives as a streaming zipfile."""

    content_type = "application/zip"
    AS_ATTACHMENT = True
    TARGET: str = "download"

    @override
    def get_object(self):
        """Get comic paths for a browse group."""
        group = self.kwargs.get("group")
        pks = self.kwargs.get("pks")
        if not self.model:
            reason = f"Could not find model for group {group}"
            return HttpResponseBadRequest(reason)

        try:
            qs = self.get_filtered_queryset(self.model, group=group, pks=pks)
            path_rel = self.rel_prefix + "path"
            paths = qs.values_list(path_rel, flat=True)
        except Exception as exc:
            logger.warning(f"Error with download query for {group}:{pks} {exc}")
            raise

        if not paths:
            reason = f"Comics from {group}:{pks} not not found."
            raise Http404(reason)

        return sorted(set(paths))

    @extend_schema(responses={(200, content_type): OpenApiTypes.BINARY})
    def get(self, *_args, **kwargs):
        """Stream a zip archive of many comics."""
        paths = self.get_object()

        zs = ZipStream(sized=True)
        for path in paths:
            zs.add_path(path)
        download_file = zs

        filename = kwargs.get("filename")
        if not filename:
            pks = self.kwargs.get("pks")
            name = self.model.__name__ if self.model else "No Model"
            filename = f"{name} {pks} Comics.zip"

        headers = {"Content-Length": len(zs), "Last-Modified": zs.last_modified}
        return FileResponse(
            download_file,
            as_attachment=self.AS_ATTACHMENT,
            content_type=self.content_type,
            filename=filename,
            headers=headers,
        )
