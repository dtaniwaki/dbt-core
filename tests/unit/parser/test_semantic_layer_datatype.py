import json
from pathlib import Path

import pytest
from metricflow_semantic_interfaces.implementations.elements.dimension import (
    PydanticDimension,
)
from metricflow_semantic_interfaces.type_enums import DataType

from dbt.artifacts.resources import Dimension
from dbt.contracts.graph.unparsed import (
    UnparsedDimension,
    UnparsedDimensionV2,
    UnparsedMetric,
    UnparsedMetricV2,
)
from dbt.parser.schema_yaml_readers import SemanticModelParser
from dbt_common.dataclass_schema import ValidationError

MANIFEST_SCHEMA_PATH = Path(__file__).parents[3] / "schemas" / "dbt" / "manifest" / "v12.json"

METRIC_DICT = {
    "name": "revenue",
    "label": "Revenue",
    "type": "simple",
    "type_params": {"measure": "revenue"},
}
METRIC_V2_DICT = {"name": "revenue", "type": "simple", "agg": "sum"}
METRIC_CASES = [(UnparsedMetric, METRIC_DICT), (UnparsedMetricV2, METRIC_V2_DICT)]


def _parse(unparsed: UnparsedDimension) -> Dimension:
    return SemanticModelParser.__new__(SemanticModelParser)._get_dimensions([unparsed])[0]


DATATYPES = [
    "string",
    "integer",
    "decimal",
    "float",
    "boolean",
    "date",
    "time",
    "datetime",
    "datetime_tz",
    "opaque",
]


def _datatype_enums_in_manifest_schema() -> list:
    with open(MANIFEST_SCHEMA_PATH) as fp:
        schema = json.load(fp)
    found = []

    def walk(node) -> None:
        if isinstance(node, dict):
            datatype = node.get("datatype")
            if isinstance(datatype, dict):
                found.append(next(o["enum"] for o in datatype.get("anyOf", []) if "enum" in o))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(schema)
    return found


class TestDatatypeValues:
    def test_datatype_enum_matches_accepted_values(self):
        assert [member.value for member in DataType] == DATATYPES

    def test_manifest_schema_lists_the_same_values(self):
        enums = _datatype_enums_in_manifest_schema()
        assert len(enums) == 4
        assert all(enum == DATATYPES for enum in enums)


class TestDimensionDatatype:
    @pytest.mark.parametrize("datatype", DATATYPES)
    def test_unparsed_dimension_accepts_every_datatype(self, datatype):
        unparsed = UnparsedDimension.from_dict(
            {"name": "is_active", "type": "categorical", "datatype": datatype}
        )
        assert unparsed.datatype == DataType(datatype)

    def test_unparsed_dimension_defaults_datatype_to_none(self):
        unparsed = UnparsedDimension.from_dict({"name": "is_active", "type": "categorical"})
        assert unparsed.datatype is None

    @pytest.mark.parametrize("datatype", ["bool", "BOOLEAN", 1])
    def test_unparsed_dimension_rejects_unknown_datatype(self, datatype):
        with pytest.raises(ValidationError):
            UnparsedDimension.validate(
                {"name": "is_active", "type": "categorical", "datatype": datatype}
            )

    def test_unparsed_dimension_rejects_unknown_field(self):
        with pytest.raises(ValidationError):
            UnparsedDimension.validate(
                {"name": "is_active", "type": "categorical", "data_type": "boolean"}
            )

    def test_unparsed_dimension_v2_rejects_datatype(self):
        with pytest.raises(ValidationError, match="datatype"):
            UnparsedDimensionV2.validate(
                {"type": "categorical", "name": "a", "datatype": "string"}
            )

    def test_datatype_is_passed_to_dimension(self):
        dimension = _parse(
            UnparsedDimension(name="is_active", type="categorical", datatype=DataType.BOOLEAN)
        )
        assert dimension.datatype == DataType.BOOLEAN

    def test_omitted_datatype_defaults_to_none(self):
        dimension = _parse(UnparsedDimension(name="is_active", type="categorical"))
        assert dimension.datatype is None

    def test_dimension_converts_to_pydantic_dimension(self):
        dimension = _parse(
            UnparsedDimension(name="is_active", type="categorical", datatype=DataType.BOOLEAN)
        )
        pydantic_dimension = PydanticDimension.parse_obj(dimension.to_dict())
        assert pydantic_dimension.datatype == DataType.BOOLEAN


class TestMetricDatatype:
    @pytest.mark.parametrize("unparsed_type, base_dict", METRIC_CASES)
    def test_unparsed_metric_accepts_datatype(self, unparsed_type, base_dict):
        unparsed = unparsed_type.from_dict({**base_dict, "datatype": "decimal"})
        assert unparsed.datatype == DataType.DECIMAL

    @pytest.mark.parametrize("unparsed_type, base_dict", METRIC_CASES)
    def test_unparsed_metric_defaults_datatype_to_none(self, unparsed_type, base_dict):
        assert unparsed_type.from_dict(base_dict).datatype is None

    @pytest.mark.parametrize("unparsed_type, base_dict", METRIC_CASES)
    def test_unparsed_metric_rejects_unknown_datatype(self, unparsed_type, base_dict):
        with pytest.raises(ValidationError):
            unparsed_type.validate({**base_dict, "datatype": "money"})

    @pytest.mark.parametrize("unparsed_type, base_dict", METRIC_CASES)
    def test_unparsed_metric_rejects_unknown_field(self, unparsed_type, base_dict):
        with pytest.raises(ValidationError):
            unparsed_type.validate({**base_dict, "data_type": "decimal"})
