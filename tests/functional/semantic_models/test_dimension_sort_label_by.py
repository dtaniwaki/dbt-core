import json
import os
from typing import List

import pytest
from metricflow_semantic_interfaces.implementations.elements.dimension import (
    PydanticDimension,
)

from dbt.contracts.graph.manifest import Manifest
from dbt.tests.util import run_dbt
from dbt_common.events.base_types import BaseEvent
from tests.functional.assertions.test_runner import dbtTestRunner
from tests.functional.semantic_models.fixtures import simple_metricflow_time_spine_sql

requires_sort_by_support = pytest.mark.skipif(
    "sort_by" not in PydanticDimension.__fields__,
    reason="the installed MetricFlow does not support Dimension.sort_by",
)

requires_sort_by_support = pytest.mark.skipif(
    "sort_by" not in PydanticDimension.__fields__,
    reason="the installed MetricFlow does not support Dimension.sort_by",
)

products_sql = """
select
  1 as id,
  'C01' as category_code,
  2 as category_rank,
  'Beverages' as category_name,
  current_timestamp as created_at
"""

semantic_model_with_sort_label_by_yml = """
version: 2

semantic_models:
  - name: products
    model: ref('products')
    entities:
      - name: product
        type: primary
        expr: id
    dimensions:
      - name: category_code
        type: categorical
        sort_by: category_rank
        label_by: category_name
      - name: category_rank
        type: categorical
      - name: category_name
        type: categorical
      - name: created_at
        type: time
        type_params:
          time_granularity: day
    measures:
      - name: product_count
        agg: count
        expr: id
        agg_time_dimension: created_at
        create_metric: true
"""

semantic_model_without_sort_label_by_yml = semantic_model_with_sort_label_by_yml.replace(
    "        sort_by: category_rank\n", ""
).replace("        label_by: category_name\n", "")


def read_semantic_manifest_dimensions(project) -> dict:
    with open(os.path.join(project.project_root, "target", "semantic_manifest.json")) as fp:
        semantic_manifest = json.load(fp)
    products = next(sm for sm in semantic_manifest["semantic_models"] if sm["name"] == "products")
    return {dimension["name"]: dimension for dimension in products["dimensions"]}


def models_with(yml: str):
    return {
        "products.sql": products_sql,
        "metricflow_time_spine.sql": simple_metricflow_time_spine_sql,
        "semantic_models.yml": yml,
    }


class TestDimensionSortByAndLabelBy:
    @pytest.fixture(scope="class")
    def models(self):
        return models_with(semantic_model_with_sort_label_by_yml)

    def test_sort_by_and_label_by_reach_manifest(self, project):
        manifest = run_dbt(["parse"])
        assert isinstance(manifest, Manifest)

        dimensions = {
            dimension.name: dimension
            for dimension in manifest.semantic_models["semantic_model.test.products"].dimensions
        }
        assert dimensions["category_code"].sort_by == "category_rank"
        assert dimensions["category_code"].label_by == "category_name"
        assert dimensions["category_rank"].sort_by is None
        assert dimensions["category_rank"].label_by is None


@requires_sort_by_support
class TestSemanticManifestDimensionSortByAndLabelBy:
    @pytest.fixture(scope="class")
    def models(self):
        return models_with(semantic_model_with_sort_label_by_yml)

    def test_sort_by_and_label_by_reach_semantic_manifest(self, project):
        run_dbt(["parse"])
        semantic_dimensions = read_semantic_manifest_dimensions(project)
        assert semantic_dimensions["category_code"]["sort_by"] == "category_rank"
        assert semantic_dimensions["category_code"]["label_by"] == "category_name"


@requires_sort_by_support
class TestSemanticManifestDimensionWithoutSortByAndLabelBy:
    @pytest.fixture(scope="class")
    def models(self):
        return models_with(semantic_model_without_sort_label_by_yml)

    def test_omitted_fields_are_null(self, project):
        run_dbt(["parse"])
        semantic_dimensions = read_semantic_manifest_dimensions(project)
        assert semantic_dimensions["category_code"]["sort_by"] is None
        assert semantic_dimensions["category_code"]["label_by"] is None


@requires_sort_by_support
class TestDimensionSortByWithUnknownDimension:
    @pytest.fixture(scope="class")
    def models(self):
        return models_with(
            semantic_model_with_sort_label_by_yml.replace(
                "sort_by: category_rank", "sort_by: missing_rank"
            )
        )

    def test_unknown_sort_by_fails_parse(self, project):
        events: List[BaseEvent] = []
        result = dbtTestRunner(callbacks=[events.append]).invoke(["parse"])
        assert not result.success

        validation_errors = [e for e in events if e.info.name == "SemanticValidationFailure"]
        assert any(
            "`sort_by`" in e.info.msg and "`missing_rank`" in e.info.msg for e in validation_errors
        )
