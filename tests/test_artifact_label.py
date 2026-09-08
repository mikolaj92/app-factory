"""Run artifacts have one required display label, not a legacy name alias."""

import pytest
from pydantic import ValidationError

from app_factory.runs import RunArtifact


def test_artifact_rejects_name_and_requires_label() -> None:
    with pytest.raises(ValidationError):
        RunArtifact(id="result", media_type="text/plain", name="Legacy")
    with pytest.raises(ValidationError):
        RunArtifact(id="result", media_type="text/plain", label="", name="Legacy")


def test_serialized_artifact_has_only_label() -> None:
    artifact = RunArtifact(id="result", media_type="text/plain", label="Result")
    assert artifact.model_dump()["label"] == "Result"
    assert "name" not in artifact.model_dump()
