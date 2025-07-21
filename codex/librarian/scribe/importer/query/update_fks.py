"""Query the missing foreign keys methods."""

from comicbox.enums.comicbox import compare_identifier_source

from codex.librarian.scribe.importer.const import MODEL_REL_MAP
from codex.librarian.scribe.importer.query.filters import (
    QueryForeignKeysFilterImporter,
)
from codex.models.base import BaseModel


class QueryIsUpdateImporter(QueryForeignKeysFilterImporter):
    """Query the missing foreign keys methods."""

    @staticmethod
    def _query_missing_models_is_do_update_identifier(
        best_extra_values: tuple,
        proposed_extra_values: tuple,
        synthesized_extra_proposed_values: list,
    ):
        """Compare Identifiers."""
        best_identifier = best_extra_values[0]
        if proposed_identifier := proposed_extra_values[0]:
            if best_identifier:
                best_id_source, _, best_id_key = best_identifier
                (
                    proposed_id_source,
                    _,
                    proposed_id_key,
                ) = proposed_identifier

                if (
                    compare_identifier_source(best_id_source, proposed_id_source)
                    or best_id_key != proposed_id_key
                ):
                    best_identifier = proposed_identifier
            else:
                best_identifier = proposed_identifier

        synthesized_extra_proposed_values.append(best_identifier)

    @staticmethod
    def _query_missing_models_is_do_update_extra(
        best_extra_values: tuple,
        proposed_extra_values: tuple,
        synthesized_extra_proposed_values: list,
        *,
        has_id: bool,
    ):
        """Compare extra relations."""
        if has_id:
            best_extra_values = best_extra_values[1:]
            proposed_extra_values = proposed_extra_values[1:]
        synthesized_extra_values = []

        for best_extra_value, proposed_extra_value in zip(
            best_extra_values, proposed_extra_values, strict=True
        ):
            if (
                proposed_extra_value is not None
                and proposed_extra_value != best_extra_value
            ):
                synthesized_extra_values.append(proposed_extra_value)
            else:
                synthesized_extra_values.append(best_extra_value)

        synthesized_extra_proposed_values.extend(synthesized_extra_values)

    @staticmethod
    def _query_normalize_existing_values(
        existing_values_tuple: tuple, extra_index: int
    ):
        existing_identifier = existing_values_tuple[extra_index : extra_index + 3]
        if not any(existing_identifier):
            existing_identifier = None
        existing_extra_values = existing_values_tuple[extra_index + 3 :]
        return (existing_identifier, *existing_extra_values)

    @classmethod
    def _query_update_init_best_and_existing_values(
        cls,
        existing_extra_values_tuple: tuple | None,
        proposed_extra_values_tuples_set: set[tuple],
    ) -> tuple[tuple | None, tuple]:
        """
        Initialize first best value.

        Normalize existing values and assign to best value OR initialize best values
        with first proposed value.
        """
        if existing_extra_values_tuple:
            best_extra_values = existing_extra_values_tuple
        else:
            try:
                best_extra_values = proposed_extra_values_tuples_set.pop()
            except KeyError:
                best_extra_values = ()
        return existing_extra_values_tuple, best_extra_values

    @classmethod
    def query_model_best_extra_values(
        cls,
        model: type[BaseModel],
        existing_extra_values_tuple: tuple | None,
        proposed_extra_values_tuples_set: set[tuple],
    ) -> tuple[bool, tuple]:
        """Find possible updates from existing."""
        if not existing_extra_values_tuple and not proposed_extra_values_tuples_set:
            return False, ()
        _, id_rel, *extra_rels = MODEL_REL_MAP[model]
        existing_extra_values, best_extra_values = (
            cls._query_update_init_best_and_existing_values(
                existing_extra_values_tuple,
                proposed_extra_values_tuples_set,
            )
        )

        has_id = bool(id_rel)
        for extra_values_tuple in proposed_extra_values_tuples_set:
            synthesized_extra_proposed_values = []
            if has_id:
                cls._query_missing_models_is_do_update_identifier(
                    best_extra_values,
                    extra_values_tuple,
                    synthesized_extra_proposed_values,
                )

            if extra_rels:
                cls._query_missing_models_is_do_update_extra(
                    best_extra_values,
                    extra_values_tuple,
                    synthesized_extra_proposed_values,
                    has_id=has_id,
                )

            best_extra_values = tuple(synthesized_extra_proposed_values)

        do_update = best_extra_values != existing_extra_values

        return do_update, best_extra_values
