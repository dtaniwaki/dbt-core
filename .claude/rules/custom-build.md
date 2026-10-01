# Custom Build

Base: `2d03a13d5` (upstream `1.latest` HEAD, dbt-core 1.14.0a1)
Date: 2026-10-02

upstream の `main` は dbt v2.0（Rust 実装）になり、v1 (Python) の開発は `1.latest` ブランチに移ったため、
ベースを `v1.11.7` タグから `1.latest` に変更した。upstream リポジトリは `dbt-labs/dbt-core` から
`dbt-labs/dbt` に改名されている。

## Included PRs

- https://github.com/dbt-labs/dbt/pull/12604 — feat: add config.tags and +tags support for metrics (branch: `origin/fix/metric-project-config-tags`)
- https://github.com/dbt-labs/dbt/pull/12628 — feat: add --no-full-refresh flag to dbt compile (branch: `origin/worktree-recursive-strolling-eclipse` `42d128f80`。`1.latest` で新しい engine の環境変数は `DBT_ENGINE_` 接頭辞が必須になったため、`DBT_NO_FULL_REFRESH` を `DBT_ENGINE_NO_FULL_REFRESH` に変更)

## Conflict Resolutions

なし（2 本とも `1.latest` に追従済みで、コンフリクトなし）

## Tests

unit tests: 2202 passed / 1 failed。落ちた `tests/unit/artifacts/test_run_execution_result.py::test_run_execution_result_serialization`
は単独で流すと通ったり落ちたりする（PR の変更とは無関係）。
