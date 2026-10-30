# Custom Build

Base: `24ac090d4` (upstream `1.latest`, dbt-core 1.14.0a1)
Date: 2026-10-29

The upstream repository was renamed from `dbt-labs/dbt-core` to `dbt-labs/dbt`, and development of v1 (Python) happens on `1.latest`.

The semantic layer PRs need the matching MetricFlow build (`dtaniwaki/metricflow` branch `custom-build`): the published `metricflow` 0.213.0 does not contain `metricflow_semantic_interfaces.validations.hierarchies`, and it silently ignores the new fields.

## Included PRs

- https://github.com/dbt-labs/dbt/pull/12604 — feat: add config.tags and +tags support for metrics
- https://github.com/dbt-labs/dbt/pull/12628 — feat: add --no-full-refresh flag to dbt compile (`DBT_NO_FULL_REFRESH` is `DBT_ENGINE_NO_FULL_REFRESH` on `1.latest`)
- https://github.com/dbt-labs/dbt/pull/16577 — feat: support dimension() in exposure depends_on (including dimensions declared through a semantic model's `primary_entity`)
- https://github.com/dbt-labs/dbt/pull/16657 — feat: add dimension hierarchies to semantic models
- https://github.com/dbt-labs/dbt/pull/16660 — test: respect POSTGRES_TEST_PORT in functional tests that override the profile
- https://github.com/dtaniwaki/dbt-core/pull/2 — feat: add exclude_dimensions to metric inputs
- https://github.com/dtaniwaki/dbt-core/pull/3 — feat: add sort_by and label_by to dimensions
- https://github.com/dtaniwaki/dbt-core/pull/4 — feat: add the dimension: node selector
- https://github.com/dtaniwaki/dbt-core/pull/5 — feat: add datatype to semantic layer elements

## Conflict Resolutions

- `tests/unit/graph/test_nodes.py`: the hierarchies tests and the sort_by/label_by tests were added at the same place; both are kept.
- `core/dbt/parser/schema_yaml_readers.py`, `core/dbt/contracts/graph/unparsed.py`, `schemas/dbt/manifest/v12.json`, `tests/unit/test_semantic_manifest.py`, `tests/unit/graph/test_nodes.py`: the datatype PR and the earlier semantic layer PRs touched the same fields and schema entries; the fields of both are kept (resolved by hand).

## Verification

- `tests/unit`: 2363 passed, 10 skipped.
- Functional tests (Postgres) for semantic models, metrics, exposures, compile, graph selection and saved queries: 283 tests, 0 failed, 1 skipped.
- `schemas/dbt/manifest/v12.json` parses and has no duplicate keys; it carries `hierarchies`, `sort_by`, `label_by`, `datatype` and `exclude_dimensions`.
