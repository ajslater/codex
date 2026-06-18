# Vendored OPDS / Readium / Atom schemas

These are **upstream spec files**, committed verbatim so the OPDS
schema-compliance tests (`tests/test_opds_schema.py`) run offline and
deterministically. Do not hand-edit them — refresh with:

```bash
python tests/schema/opds/fetch_schemas.py
```

`fetch_schemas.py` pins the exact upstream commit SHAs; bump them there to
update.

## Layout

| Path                                               | Source                                                                                                                       | Notes                                           |
| -------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| `v2/opds/{feed,publication,...}.schema.json`       | [opds-community/specs](https://github.com/opds-community/specs) `schema/`                                                    | OPDS 2.0 JSON Schema (draft-07)                 |
| `v2/opds/{authentication,progression}.schema.json` | [opds-community/drafts](https://github.com/opds-community/drafts) `schema/`                                                  | Auth-for-OPDS-1.0 + OPDS Progression 1.0        |
| `v2/readium/**/*.json`                             | [readium/webpub-manifest](https://github.com/readium/webpub-manifest) `schema/`                                              | OPDS 2.0 `$ref`s into these                     |
| `v1/opds.rnc`                                      | [opds-community/specs](https://github.com/opds-community/specs) `schema/1.2/opds.rnc`                                        | OPDS 1.2 RELAX NG Compact                       |
| `v1/atom.rnc`                                      | RFC 4287 App. B (via [opengeospatial/schema-utils](https://github.com/opengeospatial/schema-utils))                          | `opds.rnc` `include`s it                        |
| `v1/opds-pse-1.2.rnc`                              | **hand-authored** from the [OPDS-PSE 1.2 spec](https://github.com/anansi-project/opds-pse/blob/master/v1.2.md)               | Page Streaming Extension (no official schema)   |
| `v1/opensearch-1.1.rnc`                            | **hand-authored** from the [OpenSearch 1.1 spec](https://github.com/dewitt/opensearch/blob/master/opensearch-1-1-draft-6.md) | OpenSearch description doc (no official schema) |

## How they're consumed

`tests/opds_schema.py` is the validator:

- **v2** — every `*.json` is loaded into a `referencing.Registry` keyed by its
  `$id`. Cross-repo `$ref`s resolve against the registry; the OPDS schemas are
  also aliased under `specs.opds.io` (Readium's `link.schema.json` refs that
  host while the OPDS files declare `$id` under `drafts.opds.io`).
- **v1.2** — `opds.rnc` (which `include`s `atom.rnc`) is read with `rnc2rng`,
  compiled to RELAX NG, and run via `lxml`. The vendored `.rnc` files stay
  pristine; the few transforms needed to make `opds.rnc` parseable by `rnc2rng`
  (data-except → `text`, typed-string → bare literal, missing namespace decls,
  stripping the illegal `xmlns:local=""`) are applied **in code** and documented
  there. `opds-pse-1.2.rnc` validates the Page Streaming Extension stream links
  extracted from each feed, and `opensearch-1.1.rnc` validates the OpenSearch
  description document at `/opds/v1.2/opensearch/v1.1`.
- **auth / progression** — the two `drafts.opds.io` JSON schemas validate the
  Authentication Document (`/opds/auth/...`) and the OPDS Progression 1.0
  document (`/opds/v2.0/.../position`).
- **profiles without a schema** — DiViNa and the OPDS 2.0 link `authenticate`
  property (discussion #43) have no published schema, so `tests/opds_schema.py`
  applies targeted checks instead.
