import json

import pytest

from dbt.tests.util import run_dbt

members_sql = """
select 1 as id, 'f' as gender, 'east' as region, current_timestamp as created_at
"""

stores_sql = """
select 1 as id, 'east' as region
"""

visits_sql = """
select 1 as id, 1 as member_id, 'web' as channel, current_timestamp as visited_at
"""

metricflow_time_spine_sql = """
select to_date('02/20/2023', 'mm/dd/yyyy') as date_day
"""

semantic_models_yml = """
version: 2

semantic_models:
  - name: members
    model: ref('members')
    defaults:
      agg_time_dimension: created_at
    entities:
      - name: member
        type: primary
        expr: id
    dimensions:
      - name: gender
        type: categorical
      - name: region
        type: categorical
      - name: created_at
        type: time
        type_params:
          time_granularity: day
    measures:
      - name: member_count
        agg: count
        expr: id

  - name: stores
    model: ref('stores')
    entities:
      - name: store
        type: primary
        expr: id
    dimensions:
      - name: region
        type: categorical

  - name: visits
    model: ref('visits')
    defaults:
      agg_time_dimension: visited_at
    entities:
      - name: visit
        type: primary
        expr: id
      - name: member
        type: foreign
        expr: member_id
    dimensions:
      - name: channel
        type: categorical
      - name: gender
        type: categorical
      - name: visited_at
        type: time
        type_params:
          time_granularity: day
    measures:
      - name: visit_count
        agg: count
        expr: id

  - name: archived
    model: ref('stores')
    config:
      enabled: false
    entities:
      - name: archive
        type: primary
        expr: id
    dimensions:
      - name: legacy_flag
        type: categorical
      - name: region
        type: categorical

metrics:
  - name: visits_per_member
    label: Visits per member
    type: derived
    type_params:
      expr: visits_total / members_total
      metrics:
        - name: visits_total
        - name: members_total
  - name: members_total
    label: Members
    type: simple
    type_params:
      measure: member_count
  - name: visits_total
    label: Visits
    type: simple
    type_params:
      measure: visit_count
"""

selectors_yml = """
selectors:
  - name: by_gender
    definition: dimension:member__gender
"""


class TestDimensionSelection:
    @pytest.fixture(scope="class")
    def models(self):
        return {
            "members.sql": members_sql,
            "stores.sql": stores_sql,
            "visits.sql": visits_sql,
            "metricflow_time_spine.sql": metricflow_time_spine_sql,
            "schema.yml": semantic_models_yml,
        }

    @pytest.fixture(scope="class")
    def selectors(self):
        return selectors_yml

    def ls(self, *args):
        return set(run_dbt(["ls", *args], expect_pass=True))

    def test_qualified_name_selects_owning_semantic_model(self, project):
        assert self.ls("--select", "dimension:member__gender") == {"semantic_model:test.members"}

    def test_unqualified_name_selects_every_declaring_semantic_model(self, project):
        assert self.ls("--select", "dimension:gender") == {
            "semantic_model:test.members",
            "semantic_model:test.visits",
        }

    def test_same_name_in_several_semantic_models_is_disambiguated_by_entity(self, project):
        assert self.ls("--select", "dimension:region") == {
            "semantic_model:test.members",
            "semantic_model:test.stores",
        }
        assert self.ls("--select", "dimension:store__region") == {"semantic_model:test.stores"}

    def test_glob(self, project):
        assert self.ls("--select", "dimension:visit__*") == {"semantic_model:test.visits"}

    def test_unknown_name_selects_nothing(self, project):
        assert self.ls("--select", "dimension:nonexistent") == set()
        assert self.ls("--select", "dimension:member__nonexistent") == set()
        assert self.ls("--select", "dimension:store__gender") == set()

    def test_graph_operators(self, project):
        assert self.ls("--select", "dimension:channel+") == {
            "semantic_model:test.visits",
            "metric:test.visits_total",
            "metric:test.visits_per_member",
        }
        assert self.ls("--select", "+dimension:channel", "--resource-type", "model") == {
            "test.visits",
        }
        assert self.ls("--select", "@dimension:store__region", "--resource-type", "model") == {
            "test.stores",
        }

    def test_at_operator_includes_ancestors_of_descendants(self, project):
        assert self.ls("--select", "+dimension:channel", "--resource-type", "semantic_model") == {
            "semantic_model:test.visits"
        }
        assert self.ls("--select", "@dimension:channel", "--resource-type", "semantic_model") == {
            "semantic_model:test.visits",
            "semantic_model:test.members",
        }

    def test_foreign_entity_is_used_when_no_semantic_model_owns_it(self, project):
        assert self.ls("--select", "dimension:member__channel") == {"semantic_model:test.visits"}

    def test_disabled_semantic_model_is_not_selected(self, project):
        assert self.ls("--select", "dimension:legacy_flag") == set()
        assert self.ls("--select", "dimension:archive__region") == set()
        assert self.ls("--select", "dimension:region") == {
            "semantic_model:test.members",
            "semantic_model:test.stores",
        }

    def test_json_output(self, project):
        lines = run_dbt(
            ["ls", "--select", "dimension:member__gender", "--output", "json"], expect_pass=True
        )
        assert [json.loads(line)["name"] for line in lines] == ["members"]
        lines = run_dbt(
            [
                "ls",
                "--select",
                "dimension:gender",
                "--output",
                "json",
                "--output-keys",
                "name resource_type",
            ],
            expect_pass=True,
        )
        assert sorted(
            (json.loads(line)["name"], json.loads(line)["resource_type"]) for line in lines
        ) == [("members", "semantic_model"), ("visits", "semantic_model")]

    def test_exclude(self, project):
        assert self.ls(
            "--select", "dimension:gender", "--exclude", "dimension:visit__channel"
        ) == {"semantic_model:test.members"}

    def test_resource_type_filter(self, project):
        assert self.ls("--select", "dimension:gender", "--resource-type", "semantic_model") == {
            "semantic_model:test.members",
            "semantic_model:test.visits",
        }
        assert self.ls("--select", "dimension:gender", "--resource-type", "model") == set()
        assert self.ls("--select", "dimension:gender+", "--resource-type", "metric") == {
            "metric:test.members_total",
            "metric:test.visits_total",
            "metric:test.visits_per_member",
        }

    def test_selectors_yml(self, project):
        assert self.ls("--selector", "by_gender") == {"semantic_model:test.members"}
