import pytest
from metricflow_semantic_interfaces.implementations.elements.dimension import (
    PydanticDimension,
)

from dbt.artifacts.resources import Dimension
from dbt.contracts.graph.unparsed import (
    UnparsedDimension,
    UnparsedDimensionV2,
    UnparsedSemanticModel,
)
from dbt.parser.schema_yaml_readers import SemanticModelParser
from dbt_common.dataclass_schema import ValidationError

requires_sort_by_support = pytest.mark.skipif(
    "sort_by" not in PydanticDimension.__fields__,
    reason="the installed MetricFlow does not support Dimension.sort_by",
)


requires_sort_by_support = pytest.mark.skipif(
    "sort_by" not in PydanticDimension.__fields__,
    reason="the installed MetricFlow does not support Dimension.sort_by",
)


def _parse(unparsed: UnparsedDimension) -> Dimension:
    return SemanticModelParser.__new__(SemanticModelParser)._get_dimensions([unparsed])[0]


class TestDimensionSortByAndLabelBy:
    def test_unparsed_dimension_accepts_sort_by_and_label_by(self):
        unparsed = UnparsedDimension.from_dict(
            {
                "name": "category_code",
                "type": "categorical",
                "sort_by": "category_rank",
                "label_by": "category_name",
            }
        )
        assert unparsed.sort_by == "category_rank"
        assert unparsed.label_by == "category_name"

    def test_unparsed_dimension_rejects_unknown_field(self):
        with pytest.raises(ValidationError):
            UnparsedDimension.validate(
                {"name": "category_code", "type": "categorical", "order_by": "category_rank"}
            )

    def test_unparsed_dimension_v2_rejects_sort_by(self):
        with pytest.raises(ValidationError, match="sort_by"):
            UnparsedDimensionV2.validate({"type": "categorical", "name": "a", "sort_by": "b"})

    def test_unparsed_dimension_v2_rejects_sort_by(self):
        with pytest.raises(ValidationError, match="sort_by"):
            UnparsedDimensionV2.validate({"type": "categorical", "name": "a", "sort_by": "b"})

    def test_sort_by_and_label_by_are_passed_to_dimension(self):
        dimension = _parse(
            UnparsedDimension(
                name="category_code",
                type="categorical",
                sort_by="category_rank",
                label_by="category_name",
            )
        )
        assert dimension.sort_by == "category_rank"
        assert dimension.label_by == "category_name"

    def test_omitted_sort_by_and_label_by_default_to_none(self):
        dimension = _parse(UnparsedDimension(name="category_code", type="categorical"))
        assert dimension.sort_by is None
        assert dimension.label_by is None

    @requires_sort_by_support
    @requires_sort_by_support
    def test_dimension_converts_to_pydantic_dimension(self):
        dimension = _parse(
            UnparsedDimension(
                name="category_code",
                type="categorical",
                sort_by="category_rank",
                label_by="category_name",
            )
        )
        pydantic_dimension = PydanticDimension.parse_obj(dimension.to_dict())
        assert pydantic_dimension.sort_by == "category_rank"
        assert pydantic_dimension.label_by == "category_name"

    def test_unparsed_semantic_model_round_trips_fields(self):
        unparsed = UnparsedSemanticModel.from_dict(
            {
                "name": "products",
                "model": "ref('products')",
                "dimensions": [
                    {"name": "category_code", "type": "categorical", "sort_by": "category_rank"}
                ],
            }
        )
        assert unparsed.dimensions[0].sort_by == "category_rank"
        assert unparsed.dimensions[0].label_by is None
