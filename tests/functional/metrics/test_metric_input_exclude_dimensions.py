import json
import os
from typing import List

import pytest

from dbt.contracts.graph.manifest import Manifest
from dbt.tests.util import run_dbt
from dbt_common.events.base_types import BaseEvent
from tests.functional.assertions.test_runner import dbtTestRunner
from tests.functional.semantic_models.fixtures import (
    base_schema_yml_v2,
    fct_revenue_sql,
    metricflow_time_spine_sql,
    simple_metricflow_time_spine_sql,
)
from tests.functional.utils import requires_metric_input_exclude_dimensions

orders_sql = """
select
  1 as id,
  'west' as region,
  100 as amount,
  current_timestamp as ordered_at
"""

semantic_models_yml = """
version: 2

semantic_models:
  - name: orders
    model: ref('orders')
    entities:
      - name: order
        type: primary
        expr: id
    dimensions:
      - name: region
        type: categorical
      - name: ordered_at
        type: time
        type_params:
          time_granularity: day
    measures:
      - name: revenue
        agg: sum
        expr: amount
        agg_time_dimension: ordered_at
"""

metrics_yml = """
metrics:
  - name: revenue
    type: simple
    type_params:
      measure: revenue
  - name: revenue_share
    type: ratio
    type_params:
      numerator: revenue
      denominator:
        name: revenue
        exclude_dimensions: [region]
  - name: revenue_vs_total
    type: derived
    type_params:
      expr: revenue / revenue_all_regions
      metrics:
        - name: revenue
        - name: revenue
          alias: revenue_all_regions
          exclude_dimensions: [region]
"""

metrics_without_exclusion_yml = """
metrics:
  - name: revenue
    type: simple
    type_params:
      measure: revenue
  - name: revenue_share
    type: ratio
    type_params:
      numerator: revenue
      denominator: revenue
  - name: revenue_vs_total
    type: derived
    type_params:
      expr: revenue / revenue_again
      metrics:
        - name: revenue
        - name: revenue
          alias: revenue_again
"""


metrics_with_filter_and_alias_yml = """
metrics:
  - name: revenue
    type: simple
    type_params:
      measure: revenue
  - name: west_revenue_share
    type: ratio
    type_params:
      numerator:
        name: revenue
        filter: "{{ Dimension('order__region') }} = 'west'"
        alias: west_revenue
      denominator:
        name: revenue
        filter: "{{ Dimension('order__region') }} is not null"
        alias: all_revenue
        exclude_dimensions: [region]
  - name: revenue_vs_total
    type: derived
    type_params:
      expr: west_revenue / all_revenue
      metrics:
        - name: revenue
          filter: "{{ Dimension('order__region') }} = 'west'"
          alias: west_revenue
        - name: revenue
          filter: "{{ Dimension('order__region') }} is not null"
          alias: all_revenue
          exclude_dimensions: [region]
"""

v2_simple_metric_yml = """
    metrics:
      - name: simple_metric
        label: Simple Metric
        type: simple
        agg: count
        expr: id
      - name: simple_metric_2
        label: Simple Metric 2
        type: simple
        agg: count
        expr: second_col
"""

v2_cumulative_with_exclude_dimensions_yml = """
      - name: cumulative_metric
        label: Cumulative Metric
        type: cumulative
        input_metric:
          name: simple_metric
          exclude_dimensions: [id_dim]
"""

v2_conversion_base_metric_with_exclude_dimensions_yml = """
      - name: conversion_metric
        label: Conversion Metric
        type: conversion
        entity: id_entity
        calculation: conversion_rate
        base_metric:
          name: simple_metric
          exclude_dimensions: [id_dim]
        conversion_metric: simple_metric_2
"""

v2_conversion_conversion_metric_with_exclude_dimensions_yml = """
      - name: conversion_metric
        label: Conversion Metric
        type: conversion
        entity: id_entity
        calculation: conversion_rate
        base_metric: simple_metric
        conversion_metric:
          name: simple_metric_2
          exclude_dimensions: [id_dim]
"""


def read_semantic_manifest(project) -> dict:
    with open(os.path.join(project.project_root, "target", "semantic_manifest.json")) as fp:
        return json.load(fp)


def metric_named(semantic_manifest: dict, name: str) -> dict:
    return next(m for m in semantic_manifest["metrics"] if m["name"] == name)


class BaseExcludeDimensions:
    metrics_yml: str

    @pytest.fixture(scope="class")
    def models(self):
        return {
            "orders.sql": orders_sql,
            "metricflow_time_spine.sql": simple_metricflow_time_spine_sql,
            "semantic_models.yml": semantic_models_yml,
            "metrics.yml": self.metrics_yml,
        }


@requires_metric_input_exclude_dimensions
class TestMetricInputExcludeDimensions(BaseExcludeDimensions):
    metrics_yml = metrics_yml

    def test_exclude_dimensions_reach_manifests(self, project):
        manifest = run_dbt(["parse"])
        assert isinstance(manifest, Manifest)

        ratio = manifest.metrics["metric.test.revenue_share"].type_params
        assert ratio.numerator.exclude_dimensions == []
        assert ratio.denominator.exclude_dimensions == ["region"]

        derived = manifest.metrics["metric.test.revenue_vs_total"].type_params
        assert [m.exclude_dimensions for m in derived.metrics] == [[], ["region"]]

        semantic_manifest = read_semantic_manifest(project)
        ratio_params = metric_named(semantic_manifest, "revenue_share")["type_params"]
        assert ratio_params["numerator"]["exclude_dimensions"] == []
        assert ratio_params["denominator"]["exclude_dimensions"] == ["region"]
        derived_params = metric_named(semantic_manifest, "revenue_vs_total")["type_params"]
        assert [m["exclude_dimensions"] for m in derived_params["metrics"]] == [[], ["region"]]


@requires_metric_input_exclude_dimensions
class TestMetricInputWithoutExcludeDimensions(BaseExcludeDimensions):
    metrics_yml = metrics_without_exclusion_yml

    def test_inputs_have_empty_exclude_dimensions(self, project):
        manifest = run_dbt(["parse"])
        ratio = manifest.metrics["metric.test.revenue_share"].type_params
        assert ratio.denominator.exclude_dimensions == []

        semantic_manifest = read_semantic_manifest(project)
        ratio_params = metric_named(semantic_manifest, "revenue_share")["type_params"]
        assert ratio_params["denominator"]["exclude_dimensions"] == []


@requires_metric_input_exclude_dimensions
class TestMetricInputExcludeDimensionsOfUnknownDimension(BaseExcludeDimensions):
    metrics_yml = metrics_yml.replace("[region]", "[country]")

    def test_unknown_dimension_fails_parse(self, project):
        events: List[BaseEvent] = []
        runner = dbtTestRunner(callbacks=[events.append])
        result = runner.invoke(["parse"])
        assert not result.success

        validation_errors = [e for e in events if e.info.name == "SemanticValidationFailure"]
        assert any("country" in e.info.msg for e in validation_errors)


class TestMetricInputUnknownKeyIsRejected(BaseExcludeDimensions):
    metrics_yml = metrics_yml.replace("exclude_dimensions", "exclude_dimension")

    def test_unknown_key_fails_parse(self, project):
        result = dbtTestRunner().invoke(["parse"])
        assert not result.success


@requires_metric_input_exclude_dimensions
class TestMetricInputExcludeDimensionsWithFilterAndAlias(BaseExcludeDimensions):
    metrics_yml = metrics_with_filter_and_alias_yml

    def test_other_fields_are_kept(self, project):
        run_dbt(["parse"])
        semantic_manifest = read_semantic_manifest(project)

        ratio_params = metric_named(semantic_manifest, "west_revenue_share")["type_params"]
        assert ratio_params["numerator"]["alias"] == "west_revenue"
        assert ratio_params["numerator"]["exclude_dimensions"] == []
        assert ratio_params["numerator"]["filter"] is not None
        assert ratio_params["denominator"]["alias"] == "all_revenue"
        assert ratio_params["denominator"]["exclude_dimensions"] == ["region"]
        assert ratio_params["denominator"]["filter"] is not None

        derived_params = metric_named(semantic_manifest, "revenue_vs_total")["type_params"]
        first, second = derived_params["metrics"]
        assert (first["alias"], first["exclude_dimensions"]) == ("west_revenue", [])
        assert (second["alias"], second["exclude_dimensions"]) == ("all_revenue", ["region"])
        assert first["filter"] is not None and second["filter"] is not None


@requires_metric_input_exclude_dimensions
class BaseExcludeDimensionsOnUnsupportedMetricType:
    metric_yml: str

    @pytest.fixture(scope="class")
    def models(self):
        return {
            "schema.yml": base_schema_yml_v2 + v2_simple_metric_yml + self.metric_yml,
            "fct_revenue.sql": fct_revenue_sql,
            "metricflow_time_spine.sql": metricflow_time_spine_sql,
        }

    def test_parse_fails(self, project):
        events: List[BaseEvent] = []
        runner = dbtTestRunner(callbacks=[events.append])
        result = runner.invoke(["parse"])
        assert not result.success

        validation_errors = [e for e in events if e.info.name == "SemanticValidationFailure"]
        assert any(
            "exclude_dimensions" in e.info.msg and "only supported" in e.info.msg
            for e in validation_errors
        )


class TestExcludeDimensionsOnCumulativeInput(BaseExcludeDimensionsOnUnsupportedMetricType):
    metric_yml = v2_cumulative_with_exclude_dimensions_yml


class TestExcludeDimensionsOnConversionBaseMetric(BaseExcludeDimensionsOnUnsupportedMetricType):
    metric_yml = v2_conversion_base_metric_with_exclude_dimensions_yml


class TestExcludeDimensionsOnConversionMetric(BaseExcludeDimensionsOnUnsupportedMetricType):
    metric_yml = v2_conversion_conversion_metric_with_exclude_dimensions_yml
