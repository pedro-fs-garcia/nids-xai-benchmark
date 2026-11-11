from pathlib import Path

from config import PROJECT_ROOT, get_settings
from core.process_runner import PythonProcessRunner
from domains.model_artifacts.repository import ModelArtifactRepository
from domains.model_artifacts.service import ModelArtifactService


def get_model_artifact_service(data_dir: Path | None = None) -> ModelArtifactService:
    settings = get_settings()
    return ModelArtifactService(
        ModelArtifactRepository(PROJECT_ROOT, data_dir or settings.derived_data_dir, settings.training_runs_dir),
        PythonProcessRunner(),
    )
