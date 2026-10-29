import json
import os

import pytest

from dbt.contracts.graph.manifest import Manifest
from dbt.tests.util import run_dbt
from tests.functional.assertions.test_runner import dbtTestRunner
from tests.functional.semantic_models.fixtures import simple_metricflow_time_spine_sql

orders_sql = """
select
  1 as id,
  'active' as status,
  100.5 as amount,
  current_timestamp as ordered_at
"""

semantic_model_with_datatype_yml = """
version: 2

semantic_models:
  - name: orders
    model: ref('orders')
    entities:
      - name: order
        type: primary
        expr: id
    dimensions:
      - name: is_active_order
        type: categorical
        expr: "status IN ('active', 'trial')"
        datatype: boolean
      - name: status
        type: categorical
      - name: ordered_at
        type: time
        datatype: datetime
        type_params:
          time_granularity: day
    measures:
      - name: revenue
        agg: sum
        expr: amount
        agg_time_dimension: ordered_at

metrics:
  - name: total_revenue
    label: Total revenue
    type: simple
    datatype: decimal
    type_params:
      measure: revenue
  - name: order_count
    label: Order count
    type: simple
    type_params:
      measure: revenue
"""

semantic_model_without_datatype_yml = (
    semantic_model_with_datatype_yml.replace("        datatype: boolean\n", "")
    .replace("        datatype: datetime\n", "")
    .replace("    datatype: decimal\n", "")
)


def models_with(yml: str):
    return {
        "orders.sql": orders_sql,
        "metricflow_time_spine.sql": simple_metricflow_time_spine_sql,
        "semantic_models.yml": yml,
    }


def read_semantic_manifest(project) -> dict:
    with open(os.path.join(project.project_root, "target", "semantic_manifest.json")) as fp:
        return json.load(fp)


def semantic_dimensions(semantic_manifest: dict) -> dict:
    orders = next(sm for sm in semantic_manifest["semantic_models"] if sm["name"] == "orders")
    return {dimension["name"]: dimension for dimension in orders["dimensions"]}


def semantic_metrics(semantic_manifest: dict) -> dict:
    return {metric["name"]: metric for metric in semantic_manifest["metrics"]}


class TestDatatypeInManifest:
    @pytest.fixture(scope="class")
    def models(self):
        return models_with(semantic_model_with_datatype_yml)

    def test_datatype_reaches_manifest(self, project):
        manifest = run_dbt(["parse"])
        assert isinstance(manifest, Manifest)

        dimensions = {
            dimension.name: dimension
            for dimension in manifest.semantic_models["semantic_model.test.orders"].dimensions
        }
        assert dimensions["is_active_order"].datatype.value == "boolean"
        assert dimensions["ordered_at"].datatype.value == "datetime"
        assert dimensions["status"].datatype is None
        assert manifest.metrics["metric.test.total_revenue"].datatype.value == "decimal"
        assert manifest.metrics["metric.test.order_count"].datatype is None

    def test_datatype_reaches_manifest_json(self, project):
        run_dbt(["parse"])
        with open(os.path.join(project.project_root, "target", "manifest.json")) as fp:
            manifest_json = json.load(fp)

        orders = manifest_json["semantic_models"]["semantic_model.test.orders"]
        dimensions = {dimension["name"]: dimension for dimension in orders["dimensions"]}
        assert dimensions["is_active_order"]["datatype"] == "boolean"
        assert dimensions["status"]["datatype"] is None
        assert manifest_json["metrics"]["metric.test.total_revenue"]["datatype"] == "decimal"
        assert manifest_json["metrics"]["metric.test.order_count"]["datatype"] is None


class TestDatatypeInSemanticManifest:
    @pytest.fixture(scope="class")
    def models(self):
        return models_with(semantic_model_with_datatype_yml)

    def test_datatype_reaches_semantic_manifest(self, project):
        run_dbt(["parse"])
        semantic_manifest = read_semantic_manifest(project)

        dimensions = semantic_dimensions(semantic_manifest)
        assert dimensions["is_active_order"]["datatype"] == "boolean"
        assert dimensions["ordered_at"]["datatype"] == "datetime"
        assert dimensions["status"]["datatype"] is None

        metrics = semantic_metrics(semantic_manifest)
        assert metrics["total_revenue"]["datatype"] == "decimal"
        assert metrics["order_count"]["datatype"] is None


class TestOmittedDatatypeIsNull:
    @pytest.fixture(scope="class")
    def models(self):
        return models_with(semantic_model_without_datatype_yml)

    def test_omitted_datatype_is_null(self, project):
        run_dbt(["parse"])
        semantic_manifest = read_semantic_manifest(project)

        assert all(d["datatype"] is None for d in semantic_dimensions(semantic_manifest).values())
        assert all(m["datatype"] is None for m in semantic_metrics(semantic_manifest).values())


class TestUnknownDimensionDatatypeFails:
    @pytest.fixture(scope="class")
    def models(self):
        return models_with(
            semantic_model_with_datatype_yml.replace("datatype: boolean", "datatype: bool")
        )

    def test_unknown_dimension_datatype_fails_parse(self, project):
        result = dbtTestRunner().invoke(["parse"])
        assert not result.success
        assert "datatype" in str(result.exception)
        assert "bool" in str(result.exception)


class TestUnknownMetricDatatypeFails:
    @pytest.fixture(scope="class")
    def models(self):
        return models_with(
            semantic_model_with_datatype_yml.replace("datatype: decimal", "datatype: money")
        )

    def test_unknown_metric_datatype_fails_parse(self, project):
        result = dbtTestRunner().invoke(["parse"])
        assert not result.success
        assert "datatype" in str(result.exception)
        assert "money" in str(result.exception)


class TestUnknownDimensionFieldStillFails:
    @pytest.fixture(scope="class")
    def models(self):
        return models_with(
            semantic_model_with_datatype_yml.replace("datatype: boolean", "data_type: boolean")
        )

    def test_unknown_dimension_field_fails_parse(self, project):
        result = dbtTestRunner().invoke(["parse"])
        assert not result.success
        assert "data_type" in str(result.exception)


class TestUnknownMetricFieldStillFails:
    @pytest.fixture(scope="class")
    def models(self):
        return models_with(
            semantic_model_with_datatype_yml.replace("datatype: decimal", "data_type: decimal")
        )

    def test_unknown_metric_field_fails_parse(self, project):
        result = dbtTestRunner().invoke(["parse"])
        assert not result.success
        assert "data_type" in str(result.exception)
