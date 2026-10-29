import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import pytest
from metricflow_semantic_interfaces.implementations.metric import PydanticMetricInput


@contextmanager
def up_one(return_path: Optional[Path] = None):
    current_path = Path.cwd()
    os.chdir("../")
    try:
        yield
    finally:
        os.chdir(return_path or current_path)


def is_aware(dt: datetime) -> bool:
    return dt.tzinfo is not None and dt.tzinfo.utcoffset(dt) is not None


requires_metric_input_exclude_dimensions = pytest.mark.skipif(
    "exclude_dimensions" not in PydanticMetricInput.__fields__,
    reason="the installed MetricFlow does not support MetricInput.exclude_dimensions",
)
