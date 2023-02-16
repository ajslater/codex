"""Aggregate metadata from comics to prepare for importing."""
from pathlib import Path
from time import time
from zipfile import BadZipFile

from comicbox.comic_archive import ComicArchive
from comicbox.exceptions import UnsupportedArchiveTypeError
from rarfile import BadRarFile

from codex.comic_field_names import COMIC_M2M_FIELD_NAMES
from codex.librarian.importer.clean_metadata import CleanMetadataMixin
from codex.librarian.importer.status import ImportStatusTypes
from codex.models import Comic, Imprint, Publisher, Series, Volume
from codex.pdf import PDF
from codex.version import COMICBOX_CONFIG


class AggregateMetadataMixin(CleanMetadataMixin):
    """Aggregate metadata from comics to prepare for importing."""

    _BROWSER_GROUPS = (Publisher, Imprint, Series, Volume)
    _BROWSER_GROUP_TREE_COUNT_FIELDS = frozenset(["volume_count", "issue_count"])

    def _get_path_metadata(self, path):
        """Get the metatada from comicbox and munge it a little."""
        md = {}
        m2m_md = {}
        group_tree_md = {}
        failed_import = {}
        try:
            if PDF.is_pdf(path):
                file_format = Comic.FileFormat.PDF
                car_class = PDF
            else:
                file_format = Comic.FileFormat.COMIC
                car_class = ComicArchive
            with car_class(path, config=COMICBOX_CONFIG, closefd=False) as car:
                md = car.get_metadata()

            md["path"] = path
            md["file_format"] = file_format
            md = self.clean_md(md)

            # Create group tree
            group_tree = []
            for group_cls in self._BROWSER_GROUPS:
                group_field = group_cls.__name__.lower()
                # some volumes are read by ComicArchive as ints, cast
                group_name = str(md.get(group_field, Publisher.DEFAULT_NAME))
                # This fixes no imprint or whatever being in md
                md[group_field] = group_name
                group_tree.append(group_name)

            # Add counts to group tree.
            groups_md = {}
            md_group_count_fields = self._BROWSER_GROUP_TREE_COUNT_FIELDS & md.keys()
            for key in md_group_count_fields:
                groups_md[key] = md.pop(key)
            group_tree_md[tuple(group_tree)] = groups_md

            # Many_to_many fields get moved into a separate dict
            md_m2m_fields = COMIC_M2M_FIELD_NAMES & md.keys()
            for field in md_m2m_fields:
                m2m_md[field] = md.pop(field)
            m2m_md["folders"] = Path(path).parents

        except (UnsupportedArchiveTypeError, BadRarFile, BadZipFile, OSError) as exc:
            self.log.warning(f"Failed to import {path}: {exc}")
            failed_import = {path: exc}
        except Exception as exc:
            self.log.warning(f"Failed to import: {path}")
            self.log.exception(exc)
            failed_import = {path: exc}
        return md, m2m_md, group_tree_md, failed_import

    @staticmethod
    def _aggregate_m2m_metadata(all_m2m_mds, m2m_md, all_fks, path):
        """Aggregate many to many metadata by ."""
        # m2m fields and fks
        all_m2m_mds[path] = m2m_md
        # aggregate fks
        for field, names in m2m_md.items():
            if field == "credits":
                if names and "credits" not in all_fks:
                    all_fks["credits"] = set()

                # for credits add the credit fks to fks
                for credit_dict in names:
                    for field, name in credit_dict.items():
                        # These fields are ambiguous because they're fks to Credit
                        #   but aren't ever in Comic so query_fks.py can
                        #   disambiguate with special code
                        if field not in all_fks:
                            all_fks[field] = set()
                        all_fks[field].add(name)
                    credit_tuple = tuple(sorted(credit_dict.items()))
                    all_fks["credits"].add(credit_tuple)
            elif field != "folders":
                if field not in all_fks:
                    all_fks[field] = set()
                all_fks[field] |= frozenset(names)

    @staticmethod
    def _none_max(a, b):
        """None aware math.max."""
        if a is not None and b is not None:
            return max(a, b)
        if a is None:
            return b
        return a

    @classmethod
    def _set_max_group_count(
        cls, all_fks, group_tree, group_md, group_class, index, count_key
    ):
        """Assign the maximum group count number."""
        group_name = group_tree[0:index]
        try:
            count = cls._none_max(
                all_fks["group_trees"][Series].get(group_name),
                group_md.get(count_key),
            )
        except Exception:
            count = None
        all_fks["group_trees"][group_class][group_name] = count

    @classmethod
    def _aggregate_group_tree_metadata(cls, all_fks, group_tree_md):
        """Aggregate group tree data by class."""
        for group_tree, group_md in group_tree_md.items():
            all_fks["group_trees"][Publisher][group_tree[0:1]] = None
            all_fks["group_trees"][Imprint][group_tree[0:2]] = None
            cls._set_max_group_count(
                all_fks, group_tree, group_md, Series, 3, "volume_count"
            )
            cls._set_max_group_count(
                all_fks, group_tree, group_md, Volume, 4, "issue_count"
            )

    def get_aggregate_metadata(self, library, all_paths):
        """Get aggregated metatada for the paths given."""
        all_mds = {}
        all_m2m_mds = {}
        all_fks = {
            "group_trees": {Publisher: {}, Imprint: {}, Series: {}, Volume: {}},
            "comic_paths": set(),
        }
        all_failed_imports = {}
        total_paths = len(all_paths)
        self.status_controller.start(ImportStatusTypes.AGGREGATE_TAGS, total_paths)
        try:
            self.log.info(
                f"Reading tags from {total_paths} comics in {library.path}..."
            )
            since = time()
            for num, path in enumerate(all_paths):
                path = str(path)
                md, m2m_md, group_tree_md, failed_import = self._get_path_metadata(path)

                if failed_import:
                    all_failed_imports.update(failed_import)
                else:
                    if md:
                        all_mds[path] = md

                    if m2m_md:
                        self._aggregate_m2m_metadata(all_m2m_mds, m2m_md, all_fks, path)

                    if group_tree_md:
                        self._aggregate_group_tree_metadata(all_fks, group_tree_md)

                since = self.status_controller.update(
                    ImportStatusTypes.AGGREGATE_TAGS, num, total_paths, since=since
                )

            all_fks["comic_paths"] = frozenset(all_mds.keys())
            self.status_controller.update(
                ImportStatusTypes.CREATE_FAILED_IMPORTS,
                0,
                len(all_failed_imports),
                notify=False,
            )
            self.log.info(f"Aggregated tags from {len(all_mds)} comics.")
        finally:
            self.status_controller.finish(ImportStatusTypes.AGGREGATE_TAGS)
        return all_mds, all_m2m_mds, all_fks, all_failed_imports
