"""Query the missing simple foreign keys."""

from logging import DEBUG, INFO

from django.db.models import Q

from codex.librarian.importer.const import (
    FK_CREATE,
    FKC_CREATE_FKS,
    QUERY_MODELS,
)
from codex.librarian.importer.query_fks.dicts import QueryForeignKeysDictModelsImporter
from codex.models.base import BaseModel
from codex.models.named import NamedModel
from codex.settings import FILTER_BATCH_SIZE


class QueryForeignKeysSimpleImporter(QueryForeignKeysDictModelsImporter):
    """Methods for querying missing simple models.."""

    def query_missing_simple_models(
        self,
        names: set,
        create_fks,
        fk_model: type[BaseModel],
        fk_field_name: str,
        status,
    ):
        """Find missing named models and folders."""
        if not names:
            return 0

        start = 0
        proposed_names = list(names)
        num_names = len(names)
        create_names = names
        num_proposed_names = len(proposed_names)

        vnp = fk_model._meta.verbose_name_plural
        title = vnp.title() if vnp else ""
        status.subtitle = title
        while start < num_proposed_names:
            # Do this in batches so as not to exceed the 1k line sqlite limit
            end = start + FILTER_BATCH_SIZE
            batch_proposed_names = proposed_names[start:end]
            filter_args = {f"{fk_field_name}__in": batch_proposed_names}
            fk_filter = Q(**filter_args)
            create_names -= self.query_existing_mds(fk_model, fk_filter)
            num_in_batch = len(batch_proposed_names)
            status.add_complete(num_in_batch)
            self.status_controller.update(status)
            start += FILTER_BATCH_SIZE

        if status:
            status.subtitle = ""

        if create_names:
            if fk_model not in create_fks:
                create_fks[fk_model] = set()
            create_fks[fk_model] |= create_names
            level = INFO
        else:
            level = DEBUG

        self.log.log(level, f"Prepared {len(create_names)} new {title}.")
        return num_names

    def query_one_simple_model(self, fk_model: type[NamedModel], status):
        """Batch query one simple model name."""
        names = self.metadata[QUERY_MODELS].pop(fk_model)
        count = self.query_missing_simple_models(
            names,
            self.metadata[FK_CREATE][FKC_CREATE_FKS],
            fk_model,
            "name",
            status,
        )
        status.add_complete(count)
        self.status_controller.update(status, notify=False)
