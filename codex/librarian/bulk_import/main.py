from codex.librarian.bulk_import.aggregate_metadata import get_metadata
from codex.librarian.bulk_import.cleanup import cleanup_database
from codex.librarian.bulk_import.create_comics import bulk_import_comics
from codex.librarian.bulk_import.create_fks import bulk_create_comic_relations


def bulk_import(library, update_paths, create_paths, delete_pks):

    mds, m2m_mds, fks = get_metadata(library.pk, update_paths | create_paths)

    bulk_create_comic_relations(library, fks)

    bulk_import_comics(library, create_paths, update_paths, mds, m2m_mds)

    cleanup_database(library, delete_pks)
