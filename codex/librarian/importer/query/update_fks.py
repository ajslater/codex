"""Query the missing foreign keys methods."""

from comicbox.identifiers import compare_identifier_source

from codex.librarian.importer.const import MODEL_REL_MAP, get_key_index
from codex.librarian.importer.query.filters import QueryForeignKeysFilterImporter
from codex.models.base import BaseModel


class QueryIsUpdateImporter(QueryForeignKeysFilterImporter):
    """Query the missing foreign keys methods."""

    @staticmethod
    def _query_missing_models_is_do_update_identifier(
        best_values: tuple,
        proposed_values: tuple,
        extra_index: int,
        synthesized_extra_proposed_values: list,
    ):
        """Compare Identifiers."""
        best_identifier = best_values[extra_index]
        if proposed_identifier := proposed_values[extra_index]:
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
        best_values: tuple,
        proposed_values: tuple,
        extra_index: int,
        synthesized_extra_proposed_values: list,
    ):
        """Compare extra relations."""
        best_extra_values = best_values[extra_index:]
        proposed_extra_values = proposed_values[extra_index:]
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
        existing_values_tuple: tuple, key_values: tuple, extra_index: int
    ):
        existing_identifier = existing_values_tuple[extra_index : extra_index + 3]
        if not any(existing_identifier):
            existing_identifier = None
        existing_extra_values = existing_values_tuple[extra_index + 3 :]
        return (*key_values, existing_identifier, *existing_extra_values)

    @classmethod
    def _query_update_init_best_and_existing_values(
        cls,
        existing_values_tuple: tuple | None,
        id_rel: str,
        key_values: tuple,
        extra_index: int,
        proposed_values_tuples_set: set[tuple],
    ) -> tuple[tuple | None, tuple]:
        if existing_values_tuple:
            if id_rel:
                existing_values = cls._query_normalize_existing_values(
                    existing_values_tuple, key_values, extra_index
                )
            else:
                existing_values = existing_values_tuple
            best_values = existing_values
        else:
            existing_values = None
            best_values = proposed_values_tuples_set.pop()
        return existing_values, best_values

    @classmethod
    def query_model_best_values(
        cls,
        model: type[BaseModel],
        key_values: tuple,
        existing_values_tuple: tuple | None,
        proposed_values_tuples_set: set[tuple],
    ) -> tuple[bool, tuple]:
        """Find possible updates from existing."""
        _, id_rel, *extra_rels = MODEL_REL_MAP[model]
        extra_index = get_key_index(model)
        existing_values, best_values = cls._query_update_init_best_and_existing_values(
            existing_values_tuple,
            id_rel,  # pyright: ignore[reportArgumentType]
            key_values,
            extra_index,
            proposed_values_tuples_set,
        )

        for values_tuple in proposed_values_tuples_set:
            synthesized_extra_proposed_values = []
            loop_extra_index = extra_index
            if id_rel:
                cls._query_missing_models_is_do_update_identifier(
                    best_values,
                    values_tuple,
                    loop_extra_index,
                    synthesized_extra_proposed_values,
                )
                loop_extra_index += 1

            if extra_rels:
                cls._query_missing_models_is_do_update_extra(
                    best_values,
                    values_tuple,
                    loop_extra_index,
                    synthesized_extra_proposed_values,
                )

            best_values = key_values + tuple(synthesized_extra_proposed_values)

        do_update = best_values != existing_values

        return do_update, best_values
